"""FastAPI app factory.

Backend must boot headless (no frontend dependency). Telemetry is
configured to export *directly* to Application Insights when
`ObservabilitySettings.app_insights_connection_string` is set;
otherwise it is a no-op so the backend-only profile boots without any
sidecar (per v2-backend.instructions.md).

Lifespan also constructs the credential + LLM provider + agents
provider **once** and stashes them on `app.state` (see
`backend/dependencies.py`). Closing them on shutdown is mandatory:
`DefaultAzureCredential`, `AIProjectClient`, and `AgentsClient` each
own an aiohttp transport.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from azure.ai.contentsafety.aio import ContentSafetyClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.monitor.opentelemetry import (
    configure_azure_monitor,
)  # pyright: ignore[reportUnknownVariableType]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.exception_handlers import install_exception_handlers
from backend.routers import admin, conversation, files, health, history, speech
from backend.core.providers.agents import registry as agents_registry
from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.llm import registry as llm_registry
from backend.core.providers.search import registry as search_registry
from backend.core.settings import AppSettings, IndexStore, NetworkSettings, get_settings

logger = logging.getLogger(__name__)


def _init_content_safety_client(
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> ContentSafetyClient | None:
    """Build the singleton ContentSafetyClient when configured, else None.

    Returns None when either `content_safety.enabled` is False OR
    `content_safety.endpoint` is empty -- the configuration gate is
    permissive (either alone is treated as 'off'), so a half-set
    operator config fails open (chat runs unguarded) rather than
    crashing boot. Consumers MUST treat None as 'screening disabled'
    and pass user input through.

    No HTTP performed at construction time -- the first network call
    happens inside `ContentSafetyGuard.screen()` at request time.
    """
    if not (settings.content_safety.enabled and settings.content_safety.endpoint):
        return None
    return ContentSafetyClient(
        endpoint=settings.content_safety.endpoint,
        credential=credential,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    conn_str = settings.observability.app_insights_connection_string.strip()
    if conn_str:
        configure_azure_monitor(connection_string=conn_str)
        logger.info("Application Insights telemetry configured.")
    else:
        logger.info("AZURE_APP_INSIGHTS_CONNECTION_STRING not set; telemetry disabled.")

    cred_key = credentials_registry.select_default(settings.identity.uami_client_id)
    cred_provider = credentials_registry.registry.get(cred_key)(settings=settings)
    credential = await cred_provider.get_credential()
    llm_provider = llm_registry.registry.get("foundry_iq")(
        settings=settings, credential=credential
    )

    # Agents provider: backs the `agent_framework` orchestrator. Always
    # constructed (the SDK client is lazy -- no HTTP session opened until
    # the first `get_client()` call), so the `langgraph` orchestrator
    # incurs zero overhead. Registry-only dispatch (Hard Rule #4); the
    # only key today is `"foundry"`. `runtime_overrides_getter` is
    # late-binding: the persisted `RuntimeConfig` is loaded a few
    # lines below, and each cold-start `create_agent` call resolves
    # the operator-editable CWYD instructions through this lambda.
    agents_provider = agents_registry.registry.get("foundry")(
        settings=settings,
        credential=credential,
        runtime_overrides_getter=lambda: getattr(app.state, "runtime_overrides", None),
    )

    app.state.credential_provider = cred_provider
    app.state.credential = credential
    app.state.llm_provider = llm_provider
    app.state.agents_provider = agents_provider
    logger.info(
        "Providers ready (credentials=%s llm=foundry_iq agents=foundry).",
        cred_key,
    )

    # Chat-history database. Always wired -- there is no "no-database"
    # mode in v2 (chat history is a Stable Core feature). The registry
    # key matches the `Literal` value of `settings.database.db_type`
    # (`cosmosdb` / `postgresql`) so dispatch is registry-only
    # (Hard Rule #4).
    database_client = databases_registry.registry.get(settings.database.db_type)(
        settings=settings,
        credential=credential,
    )
    app.state.database_client = database_client
    logger.info("Database client ready (%s).", settings.database.db_type)

    # Live-reload runtime overrides. Load the persisted
    # `RuntimeConfig` once at startup so reads survive container
    # restarts -- the PATCH route reassigns this attribute on every
    # successful upsert, but cold start needs to seed it from the
    # database. None when nothing has been persisted yet (callers
    # treat None as 'no overrides' and fall through to env defaults).
    app.state.runtime_overrides = await database_client.get_runtime_config()
    if app.state.runtime_overrides is not None:
        logger.info(
            "Runtime overrides loaded from database (updated_by=%s).",
            app.state.runtime_overrides.updated_by or "<unset>",
        )
    else:
        logger.info("No persisted runtime overrides; using env defaults.")

    # Search provider: registry dispatches by `index_store` key
    # (`AzureSearch` / `pgvector`). The two conditionals below are
    # *configuration gates and dependency assembly*, NOT provider
    # dispatch (which is the `search.create(search_key, ...)` call):
    #   - `AzureSearch` without an endpoint stays disabled so the
    #     backend-only dev profile still boots (orchestrators fall
    #     back to pass-through retrieval when `app.state.search_provider`
    #     is None -- see `providers/orchestrators/langgraph.py`).
    #   - `pgvector` needs the postgres pool injected. The pool lives
    #     on the database client and must be a single per-process
    #     instance (`pgvector` reuses the postgres pool); only the lifespan can
    #     supply it.
    search_key = settings.database.index_store
    search_provider = None
    needs_endpoint = search_key == IndexStore.AZURE_SEARCH
    if needs_endpoint and not settings.search.endpoint:
        logger.info(
            "Search disabled (key=%s, no endpoint configured); "
            "orchestrator will run in pass-through mode.",
            search_key,
        )
    else:
        search_kwargs: dict[str, Any] = {
            "settings": settings,
            "credential": credential,
        }
        if search_key == IndexStore.PGVECTOR:
            # pgvector requires the postgres pool. `ensure_pool()` lives
            # only on the postgres client; if the pgvector path is
            # selected but the database client isn't postgres, the
            # AttributeError surfaces the misconfiguration loudly
            # instead of silently failing. The two pyright suppressions
            # cover (a) `ensure_pool` not being on the `BaseDatabaseClient`
            # ABC, and (b) the `asyncpg.Pool` return type being Unknown
            # (asyncpg ships no stubs).
            search_kwargs["pool"] = (
                await database_client.ensure_pool()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            )
        search_provider = search_registry.registry.get(search_key)(**search_kwargs)
        # ensure_schema is a no-op on AzureSearch (index owned by
        # Bicep) and runs the pgvector DDL once-per-process under an
        # asyncio.Lock + readiness flag. Unconditional call keeps the
        # wiring provider-agnostic; raising here aborts lifespan startup
        # before `yield` (the app refuses to boot on a broken schema),
        # consistent with how earlier setup failures already behave.
        await search_provider.ensure_schema()
        logger.info("Search provider ready (%s).", search_key)
    app.state.search_provider = search_provider

    content_safety_client = _init_content_safety_client(settings, credential)
    app.state.content_safety_client = content_safety_client
    if content_safety_client is None:
        logger.info(
            "Content Safety disabled (enabled=%s, endpoint_set=%s).",
            settings.content_safety.enabled,
            bool(settings.content_safety.endpoint),
        )
    else:
        logger.info("Content Safety client ready.")

    try:
        yield
    finally:
        # Close in reverse order of construction. Content Safety first
        # (most recently built, no other resource depends on it), then
        # search (pgvector borrows the postgres pool owned by the
        # database client -- closing the database client first would
        # leave search with a dead pool to call `aclose()` on).
        if content_safety_client is not None:
            try:
                await content_safety_client.close()
            except Exception:  # noqa: BLE001 -- shutdown is best-effort
                logger.exception("Error closing Content Safety client.")
        if search_provider is not None:
            try:
                await search_provider.aclose()
            except Exception:  # noqa: BLE001 -- shutdown is best-effort
                logger.exception("Error closing search provider.")
        try:
            await database_client.aclose()
        except Exception:  # noqa: BLE001 -- shutdown is best-effort
            logger.exception("Error closing database client.")
        try:
            await agents_provider.aclose()
        except Exception:  # noqa: BLE001 -- shutdown is best-effort
            logger.exception("Error closing agents provider.")
        try:
            await llm_provider.aclose()
        except Exception:  # noqa: BLE001 -- shutdown is best-effort
            logger.exception("Error closing LLM provider.")
        try:
            await credential.close()
        except Exception:  # noqa: BLE001
            logger.exception("Error closing Azure credential.")


def create_app() -> FastAPI:
    """Build the FastAPI app. Imported by uvicorn and by tests."""
    app = FastAPI(
        title="CWYD v2 backend",
        version="2.0.0",
        description=(
            "Backend API for Chat With Your Data v2: retrieval-augmented "
            "chat over your own documents. Exposes health probes, the "
            "streaming chat endpoint, conversation history, speech "
            "configuration, RBAC-gated admin runtime config and document "
            "ingestion, and source-file streaming."
        ),
        openapi_tags=[
            {
                "name": "health",
                "description": (
                    "Liveness and readiness probes for the backend. The "
                    "diagnostic snapshot always returns 200; the readiness "
                    "probe returns 503 when a required dependency is down, "
                    "so orchestrators (ACA / AKS) can gate traffic."
                ),
            },
            {
                "name": "conversation",
                "description": (
                    "The chat endpoint. Runs the configured orchestrator "
                    "over the request and either streams the reasoning / "
                    "answer / citation feed as SSE or buffers a single JSON "
                    "response, chosen by the request Accept header."
                ),
            },
            {
                "name": "history",
                "description": (
                    "Conversation history: list, create, rename, and delete "
                    "conversations, append messages, and record per-message "
                    "feedback for the signed-in user. Backed by the "
                    "configured chat-history store (Cosmos DB or Postgres)."
                ),
            },
            {
                "name": "speech",
                "description": (
                    "Speech SDK configuration plus a freshly minted, "
                    "short-lived AAD bearer token so the browser can run "
                    "speech-to-text directly against Azure Speech."
                ),
            },
            {
                "name": "admin",
                "description": (
                    "RBAC-gated administration: read the runtime "
                    "configuration and apply JSON Merge Patch overrides, and "
                    "manage indexed documents (list, upload, URL ingest, "
                    "delete, and reprocess-all)."
                ),
            },
            {
                "name": "files",
                "description": (
                    "Streams an indexed source-document blob back to the "
                    "browser for inline rendering of citations."
                ),
            },
        ],
        lifespan=_lifespan,
    )

    # Sourced from typed `NetworkSettings.cors_origins`,
    # which reads the bare `BACKEND_CORS_ORIGINS` env var via
    # `validation_alias`. Empty list -> wildcard, matching the legacy
    # behavior of the previous `os.getenv` default.
    #
    # Instantiated standalone (not via `get_settings()`) so module
    # import time stays cheap and side-effect-free for tools that just
    # want `from backend.app import app`. The full `AppSettings` tree
    # validates lazily inside the lifespan, where DB / Foundry env
    # checks belong.
    network = NetworkSettings()
    origins = list(network.cors_origins) or ["*"]
    # CORS spec forbids `Access-Control-Allow-Credentials: true` paired
    # with a wildcard origin. Browsers silently drop credentials in
    # that combo, so flip credentials off when origins is wide-open.
    allow_credentials = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(conversation.router)
    app.include_router(history.router)
    app.include_router(speech.router)
    app.include_router(admin.router)
    app.include_router(files.router)
    install_exception_handlers(app)
    return app


app = create_app()
