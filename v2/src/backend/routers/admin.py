"""Admin router.

Pillar: Stable Core
Phase: 5 (tasks #35a, #35b, #35c, #35e, #39)

Read-only operator surface for the v2 backend. Today exposes:

* ``GET /api/admin/status`` -- sanitized snapshot of the running
  configuration (orchestrator key, db type, vector index store,
  environment, deployment names, feature-enabled flags, CORS list,
  app version). Surfaces only **non-secret** values: tenant ids,
  UAMI ids, and full database / Cosmos endpoints stay out of the
  payload (covered by ``test_status_does_not_leak_sensitive_settings``).

* ``GET /api/admin/config`` and ``PATCH /api/admin/config`` --
  read / write the runtime-toggle subset of ``AppSettings`` (#35b/c).

* ``GET /api/admin/config/effective`` -- merged view of env defaults
  overlaid with persisted ``RuntimeConfig`` overrides + per-field
  provenance hints (#35e(b)). Reads the override side via the
  live-reload channel (#35e(a)) so PATCHes are visible immediately.

Auth gating (#39, RBAC-narrowed): every admin route is gated on the
shared :func:`backend.dependencies.requires_role` factory bound to
the ``"admin"`` role claim. The factory:

* Reads Easy Auth ``x-ms-client-principal`` (base64 JSON claims) +
  ``x-ms-client-principal-id`` headers.
* Returns the caller's Entra object id when the ``"admin"`` role
  claim is present.
* Raises ``401`` when Easy Auth is missing or malformed in production
  (must fail closed) and ``403`` when the caller is authenticated but
  lacks the role.
* Falls back to ``"local-dev"`` when no Easy Auth headers are present
  in ``settings.environment == "local"`` so the admin panel is
  exercisable end-to-end during development without forging claims.

The dependency callable is cached at module import (``_REQUIRE_ADMIN_USER``)
so ``app.dependency_overrides`` keying stays deterministic across
test fixtures.
"""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from backend.dependencies import (
    DatabaseClientDep,
    RuntimeOverridesDep,
    SettingsDep,
    requires_role,
)
from backend.core.types import AdminAuditEntry, RuntimeConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


_APP_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# Closed-set enums (Hard Rule #11 -- closed-set string literals are StrEnums,
# not Literals, so producer-side identity dispatch (`is ConfigSource.ENV`)
# is available and JSON wire shape is preserved unchanged (StrEnum subclasses
# str -> Pydantic serializes members to their `.value` string).
# ---------------------------------------------------------------------------


class ConfigSource(StrEnum):
    """Provenance of an `EffectiveAdminConfig.sources` entry.

    `ENV` -- value comes from the `AppSettings` env default snapshot.
    `OVERRIDE` -- value comes from the persisted `RuntimeConfig` row
    loaded into `app.state.runtime_overrides` by the lifespan +
    PATCH writeback channel.
    """

    ENV = "env"
    OVERRIDE = "override"


# ---------------------------------------------------------------------------
# Auth gate (#39 -- RBAC narrowed to the "admin" Easy Auth role claim)
#
# Cached at import time so `app.dependency_overrides[_REQUIRE_ADMIN_USER]`
# keying stays deterministic. Each `requires_role("admin")` invocation
# returns a fresh callable, so reaching for the factory at every test
# fixture would defeat dependency_overrides.
# ---------------------------------------------------------------------------


_REQUIRE_ADMIN_USER = requires_role("admin")


AdminUserIdDep = Annotated[str, Depends(_REQUIRE_ADMIN_USER)]


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
      ``backend/core/settings.py``); the OpenAI / Search / Observability
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


class EffectiveAdminConfig(BaseModel):
    """Merged effective view of `AdminConfig` (#35e(b)).

    Combines the env-default snapshot returned by
    ``GET /api/admin/config`` with the persisted `RuntimeConfig`
    overrides loaded into ``app.state.runtime_overrides`` by the
    lifespan + PATCH writeback channel from #35e(a). Each field on
    `values` is resolved by the rule:

    * Override field is `None` (the cold default and the post-clear
      state once an admin has PATCHed `null`) -> source is `"env"`,
      value comes from `AppSettings`.
    * Override field carries a non-None value -> source is
      `"override"`, value comes from `app.state.runtime_overrides`.

    The frontend renders `sources` as per-field provenance hints
    ("this is from env" / "operator overrode this on YYYY-MM-DD")
    so admins can tell at a glance which knobs are actively being
    held by an override vs. tracking the deployed env baseline.

    `updated_at` / `updated_by` surface the audit fields from the
    override row when one exists (even when every field is `None` --
    the row is the receipt that the operator interacted with the
    config); both are `None` on cold start when no override row
    has been persisted yet.
    """

    values: AdminConfig
    sources: dict[str, ConfigSource]
    updated_at: str | None = None
    updated_by: str | None = None


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


@router.get("/config/effective", response_model=EffectiveAdminConfig)
async def config_effective_endpoint(
    settings: SettingsDep,
    overrides: RuntimeOverridesDep,
    _user: AdminUserIdDep,
) -> EffectiveAdminConfig:
    """Return env defaults overlaid with persisted overrides + per-field
    provenance hints (#35e(b)).

    Reads the override side via the live-reload channel
    (`get_runtime_overrides` -> `request.app.state.runtime_overrides`)
    seeded by the lifespan loader and refreshed by every successful
    PATCH (#35e(a)), so this endpoint reflects PATCHes immediately
    without a database round-trip.
    """
    # Env defaults -- same 6-field surface as `GET /api/admin/config`.
    env_values: dict[str, Any] = {
        "orchestrator_name": settings.orchestrator.name,
        "openai_temperature": settings.openai.temperature,
        "openai_max_tokens": settings.openai.max_tokens,
        "search_use_semantic_search": settings.search.use_semantic_search,
        "search_top_k": settings.search.top_k,
        "log_level": settings.observability.log_level,
    }
    merged: dict[str, Any] = dict(env_values)
    sources: dict[str, ConfigSource] = {
        name: ConfigSource.ENV for name in env_values
    }
    if overrides is not None:
        for name in env_values:
            override_value = getattr(overrides, name)
            # `None` means "not overridden, fall through to env default"
            # (the storage shape uses `T | None = None` per RuntimeConfig
            # docstring); only non-None values count as overrides.
            if override_value is not None:
                merged[name] = override_value
                sources[name] = ConfigSource.OVERRIDE

    # Surface audit fields whenever an override row exists, even if
    # every field has been cleared back to env -- the row itself is
    # the receipt that an operator interacted with the config.
    updated_at: str | None = None
    updated_by: str | None = None
    if overrides is not None:
        updated_at = overrides.updated_at or None
        updated_by = overrides.updated_by or None

    return EffectiveAdminConfig(
        values=AdminConfig(**merged),
        sources=sources,
        updated_at=updated_at,
        updated_by=updated_by,
    )


# ---------------------------------------------------------------------------
# PATCH /api/admin/config -- runtime overrides (#35c-4)
#
# RFC 7396 JSON Merge Patch over the same 6-field surface as GET. The
# merge is computed at the route layer (NOT pushed into the storage
# layer) so the storage contract stays a dumb full-payload overwrite
# (`upsert_runtime_config` writes whatever it's given) -- mirrors the
# `upsert_agent_id` precedent and keeps merge semantics tested in one
# place. Live-reload of `app.state.settings` is **deliberately
# deferred** -- see dev_plan #35c "Excluded" section. Operators
# observe their PATCHes immediately in the response body and on the
# next container restart; an effective-config GET that overlays the
# overrides on env defaults lands in a separate row.
# ---------------------------------------------------------------------------


# Allow-list of writable RuntimeConfig fields (the 6 mutable ones --
# `updated_at` / `updated_by` are server-set and rejected on input).
# Computed once at module import so request validation is O(1).
_WRITABLE_FIELDS: frozenset[str] = frozenset(
    name
    for name in RuntimeConfig.model_fields
    if name not in {"updated_at", "updated_by"}
)


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp with timezone suffix. Matches the
    `_utcnow_iso` shape in `backend/core/providers/databases/cosmosdb.py`
    so persisted RuntimeConfig rows are comparable across providers.
    """
    return datetime.now(UTC).isoformat()


@router.patch("/config", response_model=RuntimeConfig)
async def patch_config_endpoint(
    request: Request,
    db: DatabaseClientDep,
    user_id: AdminUserIdDep,
    payload: Annotated[dict[str, Any], Body(...)],
) -> RuntimeConfig:
    """Apply an RFC 7396 JSON Merge Patch to the persisted
    `RuntimeConfig` and return the merged shape.

    Semantics:

    * Absent JSON key -> existing override unchanged.
    * Explicit ``null`` -> override cleared (the field reverts to its
      `AppSettings` env default on the next live-reload).
    * Explicit value -> override set / replaced.
    * Unknown JSON key -> 422 (allow-list lock-in).
    * Wrong-type value -> 422 (Pydantic validation on the merged
      `RuntimeConfig`).

    The body is read as a raw `dict[str, Any]` -- not bound to a
    Pydantic model with all-optional fields -- so the route can
    distinguish 'absent' from 'explicit null' (RFC 7396 §1). A
    Pydantic-bound body would silently coerce both into `None`,
    breaking the 'undo my override' UX.
    """
    # --- Allow-list lock-in (rejects unknown fields with 422) -------------
    unknown = set(payload) - _WRITABLE_FIELDS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "msg": "Unknown field(s) in PATCH body",
                "unknown_fields": sorted(unknown),
                "allowed_fields": sorted(_WRITABLE_FIELDS),
            },
        )

    # --- Read current overrides; default to a fresh RuntimeConfig on cold
    # start so the first-ever PATCH still goes through the merge path.
    # `before` keeps the raw fetch (None on first-ever PATCH) so the
    # #35f(c) audit row can distinguish 'no prior override' from
    # 'all-cleared override'.
    before = await db.get_runtime_config()
    current = before or RuntimeConfig()
    merged_data: dict[str, Any] = current.model_dump()

    # --- Apply the patch (overwrites None when key is `null`, sets when
    # key carries a value, leaves field untouched when key is absent).
    for key, value in payload.items():
        merged_data[key] = value

    # --- Server-set audit fields -- always overwritten on every PATCH so
    # an operator probing 'what's the latest override state?' can sort
    # by `updated_at` deterministically.
    merged_data["updated_at"] = _utcnow_iso()
    merged_data["updated_by"] = user_id

    # --- Type validation on the merged shape (turns wrong-type values
    # into 422 with Pydantic's structured error detail).
    try:
        merged = RuntimeConfig.model_validate(merged_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    await db.upsert_runtime_config(merged)
    # #35e(a): Live-reload. Reassign `app.state.runtime_overrides` to
    # the same instance we just persisted so the next request's
    # `get_runtime_overrides` dependency surfaces the new override
    # without a container restart. Atomic Python attribute write --
    # no lock needed because Python's GIL makes single-attribute
    # rebinds visible-or-not, never half-applied.
    request.app.state.runtime_overrides = merged

    # #35f(c): Audit hook. Fire-and-forget append to the
    # `admin_audit` log so a future forensic query can answer
    # who / what / before / after for every successful PATCH.
    # **Best-effort policy**: a failure here MUST NOT roll back
    # the PATCH -- the override is already persisted AND
    # live-reloaded; surfacing 500 to the operator would mislead
    # them into retrying a PATCH that actually succeeded. The
    # failure is logged so the gap is observable in App Insights.
    try:
        await db.write_admin_audit(
            AdminAuditEntry(
                actor=user_id,
                action="patch_config",
                before=before,
                after=merged,
            )
        )
    except Exception:
        logger.exception(
            "write_admin_audit failed; PATCH succeeded but audit row missing",
            extra={
                "operation": "write_admin_audit",
                "actor": user_id,
                "action": "patch_config",
            },
        )

    return merged


__all__ = [
    "AdminConfig",
    "AdminStatus",
    "ConfigSource",
    "EffectiveAdminConfig",
    "router",
]
