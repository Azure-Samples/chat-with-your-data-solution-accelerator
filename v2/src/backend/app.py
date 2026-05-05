"""FastAPI app factory.

Pillar: Stable Core
Phase: 2

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
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import conversation, health, history
from shared.providers import agents, credentials, databases, llm, search
from shared.settings import NetworkSettings, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    conn_str = settings.observability.app_insights_connection_string.strip()
    if conn_str:
        # Local import: keeps the backend-only profile importable even
        # if the OTel extras are not yet wheel-resolved in dev.
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn_str)
        logger.info("Application Insights telemetry configured.")
    else:
        logger.info(
            "AZURE_APP_INSIGHTS_CONNECTION_STRING not set; telemetry disabled."
        )

    cred_key = credentials.select_default(settings.identity.uami_client_id)
    cred_provider = credentials.create(cred_key, settings=settings)
    credential = await cred_provider.get_credential()
    llm_provider = llm.create(
        "foundry_iq", settings=settings, credential=credential
    )

    # Agents provider: backs the `agent_framework` orchestrator. Always
    # constructed (the SDK client is lazy -- no HTTP session opened until
    # the first `get_client()` call), so the `langgraph` orchestrator
    # incurs zero overhead. Registry-only dispatch (Hard Rule #4); the
    # only key today is `"foundry"`.
    agents_provider = agents.create(
        "foundry", settings=settings, credential=credential
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
    database_client = databases.create(
        settings.database.db_type,
        settings=settings,
        credential=credential,
    )
    app.state.database_client = database_client
    logger.info("Database client ready (%s).", settings.database.db_type)

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
    #     instance (see Phase 4 task #30); only the lifespan can
    #     supply it.
    search_key = settings.database.index_store
    search_provider = None
    needs_endpoint = search_key == "AzureSearch"
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
        if search_key == "pgvector":
            # pgvector requires the postgres pool. `ensure_pool()` lives
            # only on the postgres client; if the pgvector path is
            # selected but the database client isn't postgres, the
            # AttributeError surfaces the misconfiguration loudly
            # instead of silently failing.
            search_kwargs["pool"] = await database_client.ensure_pool()
        search_provider = search.create(search_key, **search_kwargs)
        logger.info("Search provider ready (%s).", search_key)
    app.state.search_provider = search_provider

    try:
        yield
    finally:
        # Close in reverse order of construction. Search first because
        # pgvector borrows the postgres pool owned by the database
        # client -- closing the database client first would leave
        # search with a dead pool to call `aclose()` on.
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
        lifespan=_lifespan,
    )

    # Sourced from typed `NetworkSettings.cors_origins` (CU-002b),
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
    return app


app = create_app()
