"""FastAPI dependency-injection wiring.

Pillar: Stable Core
Phase: 2

Single source of truth for how routers obtain settings, credentials,
and providers. Routers MUST go through `Depends(...)` -- no module-
level singletons, no env-var reads inside route handlers.

Lifecycle: the credential and the LLM provider are constructed **once**
during app startup (`backend/app.py::_lifespan`) and stashed on
`request.app.state`. DI just hands them out. This avoids opening a
fresh aiohttp transport on every request (DefaultAzureCredential is
*not* free to construct) and lets shutdown deterministically close
both objects.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from shared.providers.agents.base import BaseAgentsProvider
from shared.providers.credentials.base import BaseCredentialProvider
from shared.providers.databases.base import BaseDatabaseClient
from shared.providers.llm.base import BaseLLMProvider
from shared.providers.search.base import BaseSearch
from shared.settings import AppSettings, get_settings


def get_app_settings() -> AppSettings:
    """Return the cached `AppSettings` singleton."""
    return get_settings()


SettingsDep = Annotated[AppSettings, Depends(get_app_settings)]


def get_credential_provider(request: Request) -> BaseCredentialProvider:
    """Return the credential provider stashed on `app.state` at startup.

    The selection heuristic (`select_default()`) runs once during
    lifespan; routers and tests get the same instance for the life of
    the app.
    """
    provider = getattr(request.app.state, "credential_provider", None)
    if provider is None:
        raise RuntimeError(
            "credential_provider missing on app.state -- lifespan did not run."
        )
    return provider


CredentialProviderDep = Annotated[
    BaseCredentialProvider, Depends(get_credential_provider)
]


def get_llm_provider(request: Request) -> BaseLLMProvider:
    """Return the LLM provider stashed on `app.state` at startup."""
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        raise RuntimeError(
            "llm_provider missing on app.state -- lifespan did not run."
        )
    return provider


LLMProviderDep = Annotated[BaseLLMProvider, Depends(get_llm_provider)]


def get_search_provider(request: Request) -> BaseSearch | None:
    """Return the optional search provider stashed on `app.state` at startup.

    Returns ``None`` when no search backend is configured -- the chat
    orchestrators (`langgraph`, `agent_framework`) treat search as
    optional and fall back to pass-through retrieval. Lifespan
    constructs `app.state.search_provider` only when
    `settings.search.endpoint` is populated; tests can override this
    dependency directly via `app.dependency_overrides`.
    """
    return getattr(request.app.state, "search_provider", None)


SearchProviderDep = Annotated[BaseSearch | None, Depends(get_search_provider)]


def get_database_client(request: Request) -> BaseDatabaseClient:
    """Return the database client stashed on `app.state` at startup.

    Lifespan always constructs a database client (`cosmosdb` or
    `postgresql`) -- chat history is a Stable Core feature with no
    "disabled" mode. Tests can override this dependency directly via
    `app.dependency_overrides`.
    """
    client = getattr(request.app.state, "database_client", None)
    if client is None:
        raise RuntimeError(
            "database_client missing on app.state -- lifespan did not run."
        )
    return client


DatabaseClientDep = Annotated[BaseDatabaseClient, Depends(get_database_client)]


def get_agents_provider(request: Request) -> BaseAgentsProvider:
    """Return the agents provider stashed on `app.state` at startup.

    Lifespan always constructs a `FoundryAgentsProvider` (the `agents`
    registry is small and the SDK client is built lazily on first
    `get_client()` call). Routers that select the `agent_framework`
    orchestrator pull this provider's client; routers selecting
    `langgraph` ignore it. Tests can override via
    `app.dependency_overrides`.
    """
    provider = getattr(request.app.state, "agents_provider", None)
    if provider is None:
        raise RuntimeError(
            "agents_provider missing on app.state -- lifespan did not run."
        )
    return provider


AgentsProviderDep = Annotated[
    BaseAgentsProvider, Depends(get_agents_provider)
]


__all__ = [
    "AgentsProviderDep",
    "CredentialProviderDep",
    "DatabaseClientDep",
    "LLMProviderDep",
    "SearchProviderDep",
    "SettingsDep",
    "get_agents_provider",
    "get_app_settings",
    "get_credential_provider",
    "get_database_client",
    "get_llm_provider",
    "get_search_provider",
]
