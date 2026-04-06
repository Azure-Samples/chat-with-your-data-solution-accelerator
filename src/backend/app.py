"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.env_settings import EnvSettings

from .routers import admin, auth, chat_history, conversation, files, health, speech

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("Starting CWYD API")
    settings = EnvSettings()
    app.state.settings = settings

    if settings.applicationinsights_enabled:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor()
            logger.info("Azure Monitor OpenTelemetry configured")
        except ImportError:
            logger.warning("azure-monitor-opentelemetry not installed, skipping")

    yield
    logger.info("Shutting down CWYD API")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Chat with Your Data API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(conversation.router, prefix="/api", tags=["conversation"])
    app.include_router(chat_history.router, prefix="/api", tags=["chat_history"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(speech.router, prefix="/api", tags=["speech"])
    app.include_router(files.router, prefix="/api", tags=["files"])

    return app


app = create_app()
