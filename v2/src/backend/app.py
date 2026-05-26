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

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import openai
from azure.core.exceptions import AzureError
from azure.cosmos.exceptions import CosmosHttpResponseError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routers import conversation, health, history, speech
from backend.core.providers.agents import registry as agents_registry
from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.llm import registry as llm_registry
from backend.core.providers.search import registry as search_registry
from backend.core.settings import NetworkSettings, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    conn_str = settings.observability.app_insights_connection_string.strip()
    if conn_str:
        # Local import: keeps the backend-only profile importable even
        # if the OTel extras are not yet wheel-resolved in dev.
        from azure.monitor.opentelemetry import (
            configure_azure_monitor,  # pyright: ignore[reportUnknownVariableType]
        )

        configure_azure_monitor(connection_string=conn_str)
        logger.info("Application Insights telemetry configured.")
    else:
        logger.info(
            "AZURE_APP_INSIGHTS_CONNECTION_STRING not set; telemetry disabled."
        )

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
    # only key today is `"foundry"`.
    agents_provider = agents_registry.registry.get("foundry")(
        settings=settings, credential=credential
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

    # #35e(a): Live-reload runtime overrides. Load the persisted
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
            # instead of silently failing. The two pyright suppressions
            # cover (a) `ensure_pool` not being on the `BaseDatabaseClient`
            # ABC, and (b) the `asyncpg.Pool` return type being Unknown
            # (asyncpg ships no stubs).
            search_kwargs["pool"] = (
                await database_client.ensure_pool()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            )
        search_provider = search_registry.registry.get(search_key)(**search_kwargs)
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


# ---------------------------------------------------------------------------
# App-level exception handlers (Phase C4 -- Router policy implementation)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md "Routers" row: domain
# exceptions surface as **sanitized** HTTPException-style responses
# with no SDK stack-trace, no PII, and no upstream payload echoed
# back to the client. The handlers below register on the FastAPI app
# instance once (via `_install_exception_handlers`) and apply
# uniformly to every router (conversation / history / admin / health).
#
# Why app-level (not per-route try/except)?
# - Single source of truth: one place to update the sanitized message
#   when a new SDK is added; per-route blocks drift.
# - Hard Rule #9 (clean, modular): scattering N >= 12 try/except
#   blocks across routers reproduces v1's spaghetti pattern.
# - FastAPI canonical pattern: `app.add_exception_handler(ExcType, fn)`
#   is exactly the surface the framework was designed for.
#
# Dispatch order: FastAPI walks `type(exc).__mro__` against the
# handler dict, so the most-specific class wins. `HTTPException` and
# `RequestValidationError` keep their default handlers (they live in
# their own MRO branches, not under `Exception` in our dict);
# operators and tests that already raise `HTTPException(...)` for
# 401 / 404 / 422 see the unchanged surface.
#
# Status-code rationale:
# - `openai.APIError`            -> 502 (upstream model error -- we
#                                   can't serve the request, but the
#                                   client's *input* was valid).
# - `CosmosHttpResponseError`    -> 503 (datastore transient).
# - `asyncpg.PostgresError`      -> 503 (datastore transient).
# - `AzureError`                 -> 503 (azure-search / AIProjectClient
#                                   / blob -- generic dependency).
# - `Exception` (final net)      -> 500 (unknown unhandled bug).

_OPENAI_DETAIL = "Upstream model error."
_COSMOS_DETAIL = "Database temporarily unavailable."
_POSTGRES_DETAIL = "Database temporarily unavailable."
_AZURE_DETAIL = "Azure dependency temporarily unavailable."
_INTERNAL_DETAIL = "Internal server error."


def _request_extras(request: Request) -> dict[str, Any]:
    """Build the structured logging extras for a request-scoped error.

    Reads the Easy Auth principal header directly (rather than going
    through the per-router `get_user_id` dependency) because exception
    handlers run *outside* the request's dependency injection scope.
    Empty string when absent so log records have a stable shape.
    """
    return {
        "method": request.method,
        "path": request.url.path,
        "user_id": request.headers.get("x-ms-client-principal-id", ""),
    }


async def _openai_api_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitize OpenAI / Foundry IQ failures to a 502 response."""
    logger.exception(
        "openai.APIError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=502, content={"detail": _OPENAI_DETAIL})


async def _cosmos_http_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitize Cosmos transport failures to a 503 response."""
    logger.exception(
        "CosmosHttpResponseError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _COSMOS_DETAIL})


async def _postgres_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitize asyncpg failures to a 503 response."""
    logger.exception(
        "asyncpg.PostgresError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _POSTGRES_DETAIL})


async def _azure_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitize generic azure-core failures (Search, AIProjectClient,
    Storage, etc.) to a 503 response. Registered AFTER the more
    specific `CosmosHttpResponseError` handler so MRO dispatch lands
    on the Cosmos-specific one for Cosmos errors and falls through
    here for everything else under `AzureError`.
    """
    logger.exception(
        "AzureError surfaced at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=503, content={"detail": _AZURE_DETAIL})


async def _unhandled_exception_handler(  # noqa: BLE001 -- final safety net
    request: Request, exc: Exception
) -> JSONResponse:
    """Final safety net: catch anything not covered by a more specific
    handler. Logs the full exc_info via `logger.exception` so triage
    can reconstruct from App Insights, then returns a generic 500
    body with no SDK detail leaked to the client.

    Note: `HTTPException` and `RequestValidationError` keep their
    framework defaults -- FastAPI's MRO dispatch finds those handlers
    first and never reaches this one for those types.
    """
    logger.exception(
        "unhandled exception at router boundary",
        extra={**_request_extras(request), "exception_class": type(exc).__name__},
    )
    return JSONResponse(status_code=500, content={"detail": _INTERNAL_DETAIL})


def _install_exception_handlers(app: FastAPI) -> None:
    """Register all C4 exception handlers on `app` exactly once.

    Idempotent at the FastAPI level: `add_exception_handler` overwrites
    the dict entry for a given class. Called from `create_app()` so
    every TestClient(create_app()) wired in tests gets the same
    sanitized surface.
    """
    app.add_exception_handler(openai.APIError, _openai_api_error_handler)
    app.add_exception_handler(
        CosmosHttpResponseError, _cosmos_http_error_handler
    )
    app.add_exception_handler(asyncpg.PostgresError, _postgres_error_handler)
    app.add_exception_handler(AzureError, _azure_error_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


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
    app.include_router(speech.router)
    _install_exception_handlers(app)
    return app


app = create_app()
