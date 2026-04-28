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
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import conversation, health
from providers import credentials, llm
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

    try:
        yield
    finally:
        # Close in reverse order of construction. `aclose()` on
        # FoundryIQ closes the lazily-built AIProjectClient if and only
        # if FoundryIQ owned it.
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
    return app


app = create_app()
