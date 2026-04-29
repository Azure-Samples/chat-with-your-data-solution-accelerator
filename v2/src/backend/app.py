"""FastAPI app factory.

Pillar: Stable Core
Phase: 2

Backend must boot headless (no frontend dependency). Telemetry is
configured to export *directly* to Application Insights when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is set; otherwise it is a
no-op so the backend-only profile boots without any sidecar (per
v2-backend.instructions.md).

Lifespan also constructs the credential + LLM provider **once** and
stashes them on `app.state` (see `backend/dependencies.py`). Closing
them on shutdown is mandatory: `DefaultAzureCredential` and
`AIProjectClient` each own an aiohttp transport.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import conversation, health, history
from shared.providers import credentials, databases, llm, search
from shared.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if conn_str:
        # Local import: keeps the backend-only profile importable even
        # if the OTel extras are not yet wheel-resolved in dev.
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn_str)
        logger.info("Application Insights telemetry configured.")
    else:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set; telemetry disabled.")

    settings = get_settings()
    cred_key = credentials.select_default(settings.identity.uami_client_id)
    cred_provider = credentials.create(cred_key, settings=settings)
    credential = await cred_provider.get_credential()
    llm_provider = llm.create(
        "foundry_iq", settings=settings, credential=credential
    )

    app.state.credential_provider = cred_provider
    app.state.credential = credential
    app.state.llm_provider = llm_provider
    logger.info(
        "Providers ready (credentials=%s llm=foundry_iq).", cred_key
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

    cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()] or ["*"]
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
