"""FastAPI dependency-injection wiring.

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

import logging
import uuid
from typing import Annotated

from azure.core.credentials_async import AsyncTokenCredential
from fastapi import Depends, Request

from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.credentials.base import BaseCredentialProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, get_settings
from backend.core.tools.content_safety import ContentSafetyGuard
from backend.core.tools.post_prompt import PostPromptValidator
from backend.core.types import RuntimeConfig
from backend.services.conversation import build_post_prompt_validator

logger = logging.getLogger(__name__)


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


def get_credential(request: Request) -> AsyncTokenCredential:
    """Return the lifespan-cached `AsyncTokenCredential` from app.state.

    Lifespan resolves the credential provider once (`select_default`),
    constructs a single `AsyncTokenCredential`, and stashes it on
    `app.state.credential`. Routers that need to hand a credential to
    an SDK client (e.g. the `agent_framework` orchestrator constructing
    a per-request `FoundryAgent`) reuse that same instance via this
    dep so we don't build a fresh `DefaultAzureCredential` (which is
    not free) on every request.
    """
    credential = getattr(request.app.state, "credential", None)
    if credential is None:
        raise RuntimeError("credential missing on app.state -- lifespan did not run.")
    return credential


CredentialDep = Annotated[AsyncTokenCredential, Depends(get_credential)]


def get_llm_provider(request: Request) -> BaseLLMProvider:
    """Return the LLM provider stashed on `app.state` at startup."""
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        raise RuntimeError("llm_provider missing on app.state -- lifespan did not run.")
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


AgentsProviderDep = Annotated[BaseAgentsProvider, Depends(get_agents_provider)]


def get_content_safety_guard(
    request: Request,
    settings: SettingsDep,
) -> ContentSafetyGuard | None:
    """Return a per-request ``ContentSafetyGuard``, or ``None``.

    Lifespan owns the singleton ``ContentSafetyClient`` (built behind
    the ``content_safety.enabled`` + ``endpoint`` gate). When that
    client is absent -- either the gate is open False, or lifespan
    was skipped (some ASGI test transports) -- the dep returns
    ``None`` and consumers MUST treat that as 'screening disabled'
    (pass the user input through unchanged). Returning ``None``
    rather than raising keeps content safety opt-in: a half-set or
    unset operator config fails open with no guard, not 500.

    The guard itself is cheap (no network at construction time, the
    first call happens inside ``screen()``), so building a fresh one
    per request is intentional -- it leaves room for the runtime
    override channel below to flip ``enabled`` between requests
    without rebuilding the underlying client.

    Override cascade (in order):

    * ``runtime_overrides.content_safety_enabled is False`` -> the
      operator explicitly disabled screening from the admin UI;
      return ``None`` even when the lifespan client is present.
      Operator-off ALWAYS wins.
    * ``runtime_overrides.content_safety_enabled is True`` -> defer
      to env baseline. The override cannot synthesize a client out
      of thin air (no endpoint/credential at request time), so the
      lifespan client must already exist for screening to engage.
    * ``runtime_overrides.content_safety_enabled is None`` (the
      cold default + post-clear state) -> defer to env baseline.
    * ``runtime_overrides`` attribute missing or ``None`` -> defer
      to env baseline. Runtime overrides are an optional layer.
    """
    client = getattr(request.app.state, "content_safety_client", None)
    if client is None:
        return None
    overrides = getattr(request.app.state, "runtime_overrides", None)
    if overrides is not None and overrides.content_safety_enabled is False:
        return None
    return ContentSafetyGuard(
        client=client,
        severity_threshold=settings.content_safety.severity_threshold,
    )


ContentSafetyGuardDep = Annotated[
    ContentSafetyGuard | None, Depends(get_content_safety_guard)
]


# Live-reload runtime overrides
#
# Lifespan loads the persisted ``RuntimeConfig`` from the database
# once at startup and stashes the result on
# ``request.app.state.runtime_overrides`` (None when nothing is
# persisted yet). The PATCH ``/api/admin/config`` route atomically
# reassigns the same attribute after each successful upsert, so reads
# within the same process see the new override on the very next
# request -- no container restart required.
#
# This dep is the read side of that channel. Callers MUST treat None
# as 'no overrides yet' and fall through to the env-default
# ``AppSettings`` snapshot from ``get_app_settings``. The merge step
# (effective config = env defaults + overrides) lands separately in
# ``GET /api/admin/config/effective`` so the persistence + merge
# concerns stay split.


def get_runtime_overrides(request: Request) -> RuntimeConfig | None:
    """Return the live ``RuntimeConfig`` overrides, or ``None``.

    Tolerates the ``app.state.runtime_overrides`` attribute being
    absent (e.g. ASGI test transports that skip the lifespan protocol):
    runtime overrides are a strictly optional layer on top of
    ``AppSettings``, so a missing attribute is a no-op, not a 500.
    """
    return getattr(request.app.state, "runtime_overrides", None)


RuntimeOverridesDep = Annotated[RuntimeConfig | None, Depends(get_runtime_overrides)]


def get_post_prompt_validator(
    llm: LLMProviderDep,
    overrides: RuntimeOverridesDep,
) -> PostPromptValidator | None:
    """Return a per-request ``PostPromptValidator``, or ``None``.

    Delegates the override cascade to
    :func:`backend.services.conversation.build_post_prompt_validator`:
    runtime overrides must opt in
    (``post_answering_enabled is True``) AND supply a non-empty
    ``post_answering_prompt`` template; otherwise the dep returns
    ``None`` and the chat pipeline streams without buffering. The
    post-answering knobs live only in ``RuntimeConfig`` (no
    ``AppSettings`` env baseline), so a missing
    ``app.state.runtime_overrides`` collapses to ``None`` and the
    feature stays off.
    """
    return build_post_prompt_validator(llm, overrides)


PostPromptValidatorDep = Annotated[
    PostPromptValidator | None, Depends(get_post_prompt_validator)
]


_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"
_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"


def _is_valid_guid(value: str) -> bool:
    """Return whether `value` parses as a GUID."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def get_user_id(request: Request) -> str:
    """Return the caller's user id from the principal-id header.

    Reads ``x-ms-client-principal-id`` and returns it verbatim when it
    is a valid GUID. A missing, blank, or non-GUID header falls back to
    the anonymous default id ``00000000-0000-0000-0000-000000000000``.
    Never raises: the id scopes a tenant partition, it is not a trust
    boundary.
    """
    raw = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
    if raw and _is_valid_guid(raw):
        return raw
    return _DEFAULT_USER_ID


UserIdDep = Annotated[str, Depends(get_user_id)]


__all__ = [
    "AgentsProviderDep",
    "CredentialDep",
    "CredentialProviderDep",
    "DatabaseClientDep",
    "LLMProviderDep",
    "RuntimeOverridesDep",
    "SearchProviderDep",
    "SettingsDep",
    "UserIdDep",
    "get_agents_provider",
    "get_app_settings",
    "get_credential",
    "get_credential_provider",
    "get_database_client",
    "get_llm_provider",
    "get_runtime_overrides",
    "get_search_provider",
    "get_user_id",
]
