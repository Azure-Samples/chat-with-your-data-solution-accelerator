"""Admin router request/response models.

Pillar: Stable Core
Phase: 5 (admin surface request/response models)
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.core.types import RuntimeConfig


class ConfigSource(StrEnum):
    """Provenance of an ``EffectiveAdminConfig.sources`` entry.

    ``ENV`` -- value comes from the ``AppSettings`` env default snapshot.
    ``OVERRIDE`` -- value comes from the persisted ``RuntimeConfig`` row
    loaded into ``app.state.runtime_overrides`` by the lifespan +
    PATCH writeback channel.

    Closed-set string literal modeled as ``StrEnum`` (Hard Rule #11) so
    producer-side identity dispatch (``is ConfigSource.ENV``) is
    available and JSON wire shape is preserved unchanged (``StrEnum``
    subclasses ``str`` -> Pydantic serializes members to their
    ``.value`` string).
    """

    ENV = "env"
    OVERRIDE = "override"


class AdminConfig(BaseModel):
    """Runtime-toggle subset of ``AppSettings`` (read-only view, #35b).

    The fields exposed here are exactly the settings that #35c lets
    admins mutate at runtime. Selection criteria:

    * **Not infra-pinned.** ``orchestrator.name`` lives under the
      ``CWYD_`` namespace precisely so the admin UI can flip it without
      a Bicep redeploy (see ``OrchestratorSettings`` docstring in
      ``backend/core/settings.py``); the OpenAI / Search / Observability
      tunables likewise have safe runtime defaults.
    * **Already modeled in `AppSettings`.** Each field here maps to a
      concrete attribute on `AppSettings` (so the GET handler is just
      a serialization, no `getattr` fallbacks) and is mirrored on
      `RuntimeConfig` as `T | None = None` (so PATCH semantics are
      RFC 7396-clean: `null` clears, missing leaves untouched).
      New fields must be added in lockstep across all three surfaces
      (`AppSettings`, `RuntimeConfig`, `AdminConfig`) and the PATCH
      allow-list (auto-derived from `RuntimeConfig.model_fields`).

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
    content_safety_enabled: bool


# Allow-list of writable `RuntimeConfig` fields (the mutable subset --
# `updated_at` / `updated_by` are server-set and rejected on input).
# Computed once at module import so request validation is O(1).
WRITABLE_FIELDS: frozenset[str] = frozenset(
    name
    for name in RuntimeConfig.model_fields
    if name not in {"updated_at", "updated_by"}
)


# Application version stamped into ``AdminStatus.version``. Single
# source of truth for the backend "what's deployed" value.
APP_VERSION = "2.0.0"


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


class DeleteDocumentResponse(BaseModel):
    """Response shape for ``DELETE /api/admin/documents/{source}``."""

    deleted: int = Field(
        ...,
        description="Number of indexed chunks removed for the source.",
        ge=0,
    )


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


__all__ = [
    "APP_VERSION",
    "AdminConfig",
    "AdminStatus",
    "ConfigSource",
    "DeleteDocumentResponse",
    "EffectiveAdminConfig",
    "WRITABLE_FIELDS",
]
