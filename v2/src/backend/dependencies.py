"""FastAPI dependency-injection wiring.

Pillar: Stable Core
Phase: 2 (DI seam) + Phase 5 (#39 Easy Auth role gate)

Single source of truth for how routers obtain settings, credentials,
and providers. Routers MUST go through `Depends(...)` -- no module-
level singletons, no env-var reads inside route handlers.

Lifecycle: the credential and the LLM provider are constructed **once**
during app startup (`backend/app.py::_lifespan`) and stashed on
`request.app.state`. DI just hands them out. This avoids opening a
fresh aiohttp transport on every request (DefaultAzureCredential is
*not* free to construct) and lets shutdown deterministically close
both objects.

Auth gating (`requires_role` factory) lives here too because Easy
Auth claim parsing is cross-cutting -- both the admin router (today)
and any future role-scoped endpoints reach for the same primitive
instead of each router rolling its own header-decoding helper.
"""

import base64
import binascii
import json
import logging
from collections.abc import Callable
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, Request, status

from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.credentials.base import BaseCredentialProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, Environment, get_settings
from backend.core.tools.content_safety import ContentSafetyGuard
from backend.core.types import RuntimeConfig

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


# ---------------------------------------------------------------------------
# #35e(a) -- Live-reload runtime overrides
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
# ---------------------------------------------------------------------------


def get_runtime_overrides(request: Request) -> RuntimeConfig | None:
    """Return the live ``RuntimeConfig`` overrides, or ``None``.

    Tolerates the ``app.state.runtime_overrides`` attribute being
    absent (e.g. ASGI test transports that skip the lifespan protocol):
    runtime overrides are a strictly optional layer on top of
    ``AppSettings``, so a missing attribute is a no-op, not a 500.
    """
    return getattr(request.app.state, "runtime_overrides", None)


RuntimeOverridesDep = Annotated[
    RuntimeConfig | None, Depends(get_runtime_overrides)
]


# ---------------------------------------------------------------------------
# #39 -- Easy Auth role-claim gate
#
# Replaces the Phase-5 placeholder "any authenticated caller is admin"
# rule with a proper RBAC check anchored on App Service Easy Auth
# headers. Two headers are involved:
#
# * ``x-ms-client-principal-id`` -- the caller's Entra object id (oid),
#   identical to what the chat-history router already consumes.
# * ``x-ms-client-principal``    -- a base64-encoded JSON blob carrying
#   the full claims set (including roles).
#
# Easy Auth is allowed to emit role claims under either ``typ="roles"``
# (short form) or the full schema URI; we accept both shapes so the
# gate works against AAD app-role claims and Entra ID groups-as-roles.
#
# Production semantics: missing principal id, missing/empty claims
# blob, or any decode failure -> 401 (Easy Auth must fail closed).
# Authenticated caller without the requested role -> 403.
#
# Local-dev bypass: when ``settings.environment == 'local'`` AND no
# Easy Auth headers are present, the gate returns ``"local-dev"`` so
# the admin panel is exercisable end-to-end during development without
# forging a base64 claims blob. Devs that *want* to exercise the role
# gate locally can still send the header explicitly -- the bypass is
# strictly a no-headers fallback.
# ---------------------------------------------------------------------------


_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"
_PRINCIPAL_HEADER = "x-ms-client-principal"
_LOCAL_DEV_USER = "local-dev"
_ROLE_TYP_SHORT = "roles"
_ROLE_TYP_FULL = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"


def _decode_easy_auth_principal(raw: str) -> dict[str, Any] | None:
    """Decode the base64 JSON ``x-ms-client-principal`` header.

    Returns the decoded claims dict on success or ``None`` on any
    decode failure (bad base64, non-UTF-8 bytes, malformed JSON, or
    a top-level non-object). The caller is responsible for turning
    ``None`` into an HTTP 401 -- this helper deliberately does not
    raise so the parsing logic stays unit-testable in isolation.
    """
    try:
        decoded = base64.b64decode(raw, validate=True)
        payload: object = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return cast("dict[str, Any]", payload)


def _extract_roles(principal: dict[str, Any]) -> set[str]:
    """Return the set of role values from an Easy Auth claims payload.

    Tolerant to both ``typ="roles"`` (short form) and the full URI
    role-claim ``typ`` so the gate works regardless of which Entra
    issuer flavor is configured.
    """
    roles: set[str] = set()
    claims_obj: object = principal.get("claims") or []
    if not isinstance(claims_obj, list):
        return roles
    claims = cast("list[object]", claims_obj)
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_dict = cast("dict[str, object]", claim)
        typ_obj = claim_dict.get("typ", "")
        val_obj = claim_dict.get("val", "")
        if not isinstance(typ_obj, str) or not isinstance(val_obj, str):
            continue
        if typ_obj in (_ROLE_TYP_SHORT, _ROLE_TYP_FULL) and val_obj:
            roles.add(val_obj)
    return roles


def requires_role(role: str) -> Callable[[Request, AppSettings], str]:
    """FastAPI dependency factory: gate a route on Easy Auth role claim.

    Returns a dependency function that validates the caller carries
    ``role`` in their Easy Auth claims and returns their user id
    (Entra object id) on success.

    Each call returns a NEW callable -- modules that need a stable
    key for ``app.dependency_overrides`` MUST cache the returned dep
    at module import time (see ``backend.routers.admin`` for the
    ``_REQUIRE_ADMIN_USER`` singleton pattern).
    """

    def _checker(request: Request, settings: SettingsDep) -> str:
        principal_id = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
        claims_raw = request.headers.get(_PRINCIPAL_HEADER, "").strip()

        # Local-dev bypass: no headers at all in `local` -> synthetic user.
        if not principal_id and not claims_raw:
            if settings.environment is Environment.LOCAL:
                return _LOCAL_DEV_USER
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing client principal; Easy Auth header required.",
            )

        if not claims_raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing client principal claims; "
                    "Easy Auth claims header required."
                ),
            )

        principal = _decode_easy_auth_principal(claims_raw)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed client principal payload.",
            )

        roles = _extract_roles(principal)
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required to access this resource.",
            )

        # Prefer the dedicated principal-id header (parity with
        # `history.get_user_id`); fall back to local-dev only when
        # the header is absent in local environments.
        if principal_id:
            return principal_id
        if settings.environment is Environment.LOCAL:
            return _LOCAL_DEV_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing client principal id header.",
        )

    return _checker


__all__ = [
    "AgentsProviderDep",
    "CredentialProviderDep",
    "DatabaseClientDep",
    "LLMProviderDep",
    "RuntimeOverridesDep",
    "SearchProviderDep",
    "SettingsDep",
    "get_agents_provider",
    "get_app_settings",
    "get_credential_provider",
    "get_database_client",
    "get_llm_provider",
    "get_runtime_overrides",
    "get_search_provider",
    "requires_role",
]
