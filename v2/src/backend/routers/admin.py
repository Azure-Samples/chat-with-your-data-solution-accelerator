"""Admin router.

Pillar: Stable Core
Phase: 5 (task #35a)

Read-only operator surface for the v2 backend. Today exposes:

* ``GET /api/admin/status`` -- sanitized snapshot of the running
  configuration (orchestrator key, db type, vector index store,
  environment, deployment names, feature-enabled flags, CORS list,
  app version). Surfaces only **non-secret** values: tenant ids,
  UAMI ids, and full database / Cosmos endpoints stay out of the
  payload (covered by ``test_status_does_not_leak_sensitive_settings``).

Auth gating mirrors :func:`backend.routers.history.get_user_id`
(H1 hardening, see #32b in development_plan.md §0.1):

* ``x-ms-client-principal-id`` header present -> caller id is the
  header value.
* Header missing AND ``settings.environment == "local"`` -> caller id
  is the literal ``"local-dev"`` so the panel is exercisable end-to-end
  during development.
* Header missing AND ``settings.environment == "production"`` ->
  ``401 Unauthorized``. A misconfigured Easy Auth must fail closed,
  never silently fold every anonymous caller into a single tenant.

RBAC narrowing (admin-role-only) is **deferred to task #39** with the
explicit ``# TODO(#39):`` markers below. Today every authenticated
caller is accepted.
"""

import logging
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.dependencies import SettingsDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


_LOCAL_DEV_USER = "local-dev"
_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"
_APP_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# Auth gate (mirrors history.get_user_id; RBAC narrowing -> task #39)
# ---------------------------------------------------------------------------


def admin_user_id(request: Request, settings: SettingsDep) -> str:
    """Return the admin caller's user id, or raise 401 in production.

    See module docstring for the gating contract. TODO(#39): once the
    auth router + middleware lands, narrow this dependency to require
    an admin role claim instead of any-authenticated-user.
    """
    value = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
    if value:
        return value
    if settings.environment == "local":
        return _LOCAL_DEV_USER
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing client principal; Easy Auth header required.",
    )


AdminUserIdDep = Annotated[str, Depends(admin_user_id)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AdminStatus(BaseModel):
    """Sanitized snapshot of the running configuration.

    Field allow-list is intentional: any new ``AppSettings`` field that
    surfaces here MUST be added explicitly. Sensitive settings
    (UAMI ids, tenant id, full Cosmos / Postgres connection strings,
    OpenAI API version) are deliberately omitted -- locked in by
    ``test_status_does_not_leak_sensitive_settings``.
    """

    orchestrator_name: str
    db_type: str
    index_store: str
    environment: str
    foundry_project_endpoint_host: str
    gpt_deployment: str
    embedding_deployment: str
    reasoning_deployment: str
    search_enabled: bool
    app_insights_enabled: bool
    cors_origins: list[str] = Field(default_factory=list[str])
    version: str


class AdminConfig(BaseModel):
    """Runtime-toggle subset of ``AppSettings`` (read-only view, #35b).

    The fields exposed here are exactly the settings that #35c will let
    admins mutate at runtime. Selection criteria:

    * **Not infra-pinned.** ``orchestrator.name`` lives under the
      ``CWYD_`` namespace precisely so the admin UI can flip it without
      a Bicep redeploy (see ``OrchestratorSettings`` docstring in
      ``shared/settings.py``); the OpenAI / Search / Observability
      tunables likewise have safe runtime defaults.
    * **No new settings.** Adding e.g. content-safety / RAI / post-prompt
      toggles that v1 had but v2 does not yet model would trigger
      Hard Rule #10 (new settings field) and Hard Rule #12 (out of
      this task's numeric scope) -- those land as their own §0.1 row.

    Sensitive fields (UAMI ids, tenant id, connection strings, API
    version) are **never** included; locked in by
    ``test_config_does_not_leak_sensitive_settings``.
    """

    orchestrator_name: str
    openai_temperature: float
    openai_max_tokens: int
    search_use_semantic_search: bool
    search_top_k: int
    log_level: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _host_only(url: str) -> str:
    """Return the host portion of ``url`` or empty string when unset.

    Keeps the project endpoint discoverable for operators (which
    Foundry account am I pointed at?) without leaking the full URL
    path / query, which can carry tenant or project identifiers in
    some Foundry deployment shapes.
    """
    if not url:
        return ""
    return urlparse(url).netloc


@router.get("/status", response_model=AdminStatus)
async def status_endpoint(
    settings: SettingsDep,
    _user: AdminUserIdDep,
) -> AdminStatus:
    """Return the sanitized runtime status snapshot."""
    obs_conn = settings.observability.app_insights_connection_string.strip()
    return AdminStatus(
        orchestrator_name=settings.orchestrator.name,
        db_type=settings.database.db_type,
        index_store=settings.database.index_store,
        environment=settings.environment,
        foundry_project_endpoint_host=_host_only(
            settings.foundry.project_endpoint
        ),
        gpt_deployment=settings.openai.gpt_deployment,
        embedding_deployment=settings.openai.embedding_deployment,
        reasoning_deployment=settings.openai.reasoning_deployment,
        search_enabled=bool(settings.search.endpoint),
        app_insights_enabled=bool(obs_conn),
        cors_origins=list(settings.network.cors_origins),
        version=_APP_VERSION,
    )


@router.get("/config", response_model=AdminConfig)
async def config_endpoint(
    settings: SettingsDep,
    _user: AdminUserIdDep,
) -> AdminConfig:
    """Return the runtime-toggle subset of ``AppSettings`` (#35b).

    Read-only. The mutating ``PATCH /api/admin/config`` lands in #35c
    once the persistence target (database vs in-memory) is decided
    -- see ``/memories/session/plan.md`` Q1.
    """
    return AdminConfig(
        orchestrator_name=settings.orchestrator.name,
        openai_temperature=settings.openai.temperature,
        openai_max_tokens=settings.openai.max_tokens,
        search_use_semantic_search=settings.search.use_semantic_search,
        search_top_k=settings.search.top_k,
        log_level=settings.observability.log_level,
    )


__all__ = ["AdminConfig", "AdminStatus", "admin_user_id", "router"]
