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

from providers.credentials.base import BaseCredentialProvider
from providers.llm.base import BaseLLMProvider
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


__all__ = [
    "CredentialProviderDep",
    "LLMProviderDep",
    "SettingsDep",
    "get_app_settings",
    "get_credential_provider",
    "get_llm_provider",
]
