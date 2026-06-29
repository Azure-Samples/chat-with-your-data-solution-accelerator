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

Auth gating (`requires_role` factory) lives here too because Easy
Auth claim parsing is cross-cutting -- both the admin router (today)
and any future role-scoped endpoints reach for the same primitive
instead of each router rolling its own header-decoding helper.
"""

import base64
import binascii
import json
import logging
import re
from collections.abc import Callable
from typing import Annotated, Any, cast

from azure.core.credentials_async import AsyncTokenCredential
from fastapi import Depends, HTTPException, Request, status

from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.credentials.base import BaseCredentialProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, Environment, get_settings
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
        raise RuntimeError(
            "credential missing on app.state -- lifespan did not run."
        )
    return credential


CredentialDep = Annotated[AsyncTokenCredential, Depends(get_credential)]


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
# Easy Auth *claims* header is present, the gate returns ``"local-dev"``
# so the admin panel is exercisable end-to-end during development
# without forging a base64 claims blob. The claims blob is the sole
# authority for the role check, so the forgeable principal-id header
# (which the SPA forwards by default on every call) does not defeat the
# bypass. Devs that *want* to exercise the role gate locally can still
# send the claims header explicitly.
# ---------------------------------------------------------------------------


_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"
_PRINCIPAL_HEADER = "x-ms-client-principal"
_LOCAL_DEV_USER = "local-dev"
_ROLE_TYP_SHORT = "roles"
_ROLE_TYP_FULL = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"

# Defensive allowlist for principal ids: alphanumerics plus the few
# punctuation characters that legitimately appear in Entra object ids,
# the all-zeros default user id, and the `local-dev` fallback, bounded
# to 128 characters. Anything else (control chars, whitespace,
# injection punctuation, overlong strings) is rejected before the id
# becomes a database partition key.
_PRINCIPAL_ID_PATTERN = re.compile(r"[A-Za-z0-9._@-]{1,128}")


def _is_valid_principal_id(value: str) -> bool:
    """Return whether `value` is a well-formed principal id.

    Defensive well-formedness only. A browser-forwarded principal id
    is forgeable and is therefore **not** a trust boundary -- this
    check rejects obviously-garbage values before the id is used as a
    database partition key; it does not assert that the caller is who
    the id claims to be (authenticity stays anchored on the backend's
    own Easy Auth claims, handled by `requires_role`).

    The allowlist admits Entra object ids, the all-zeros default user
    id, and the synthetic `local-dev` fallback while excluding
    everything that has no business in an identity token.
    """
    return _PRINCIPAL_ID_PATTERN.fullmatch(value) is not None


def get_user_id(request: Request, settings: SettingsDep) -> str:
    """Return the caller's user id from the Easy Auth principal-id header.

    Reads ``x-ms-client-principal-id`` (the user's Entra object id).
    When the header is absent we fall back to ``"local-dev"`` **only**
    when ``settings.environment == "local"`` so the chat-history
    panel is exercisable end-to-end during development. In
    ``production`` a missing header raises ``401 Unauthorized`` -- a
    misconfigured Easy Auth must fail closed, never silently fold
    every anonymous caller into the ``local-dev`` partition.

    Sibling of ``requires_role`` below: same Easy Auth surface, no
    role gate. Routers that only need tenant isolation (chat history)
    consume ``UserIdDep``; routers that need role enforcement (admin)
    consume ``AdminUserIdDep``.
    """
    value = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
    if value:
        if not _is_valid_principal_id(value):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed client principal id.",
            )
        return value
    if settings.environment is Environment.LOCAL:
        return _LOCAL_DEV_USER
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing client principal; Easy Auth header required.",
    )


UserIdDep = Annotated[str, Depends(get_user_id)]


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
    at module import time (see ``REQUIRE_ADMIN_USER`` below for the
    admin-role singleton).
    """

    def _checker(request: Request, settings: SettingsDep) -> str:
        principal_id = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
        claims_raw = request.headers.get(_PRINCIPAL_HEADER, "").strip()

        # The admin gate relaxes to its open posture when EITHER the
        # runtime is `local` (dev exercises the admin panel without
        # forging Easy Auth claims) OR `require_admin_auth` is False (the
        # deployment opted out of the admin wall -- the MACAE-faithful
        # default). When neither holds, a missing or insufficient
        # principal fails closed with 401. A present claims blob is
        # always role-checked regardless of this toggle, so the flag
        # relaxes the auth wall without ever bypassing role enforcement.
        allow_open_admin = (
            settings.environment is Environment.LOCAL
            or not settings.require_admin_auth
        )

        # The open-admin bypass keys on the ABSENT CLAIMS blob -- the
        # sole authority for the role check -- not on both headers being
        # absent. The SPA forwards a default principal-id on every call
        # (its shared `userIdHeaders()` seam), so the forgeable id header
        # may ride along with no claims and must not defeat the bypass.
        if not claims_raw:
            if allow_open_admin:
                return _LOCAL_DEV_USER
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
        # `history.get_user_id`); fall back to the open-admin user only
        # when the header is absent and the gate is in its open posture.
        if principal_id:
            return principal_id
        if allow_open_admin:
            return _LOCAL_DEV_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing client principal id header.",
        )

    return _checker


# Cached admin auth gate. ``requires_role("admin")`` returns a fresh
# callable on every call, so a stable key for
# ``app.dependency_overrides`` requires caching the dep once at module
# import. ``REQUIRE_ADMIN_USER`` is that singleton; ``AdminUserIdDep``
# is the typed alias routers attach to admin-gated route signatures.
REQUIRE_ADMIN_USER = requires_role("admin")
AdminUserIdDep = Annotated[str, Depends(REQUIRE_ADMIN_USER)]


__all__ = [
    "AdminUserIdDep",
    "AgentsProviderDep",
    "CredentialDep",
    "CredentialProviderDep",
    "DatabaseClientDep",
    "LLMProviderDep",
    "REQUIRE_ADMIN_USER",
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
    "requires_role",
]
