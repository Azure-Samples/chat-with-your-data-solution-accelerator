"""Admin router request/response models.

Pillar: Stable Core
Phase: 5 (admin surface request/response models)
"""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.core.providers.search.base import SourceListing
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


class ListDocumentsResponse(BaseModel):
    """Response shape for ``GET /api/admin/documents``.

    ``documents`` is service-side sorted by source (alphabetical) so
    the FE grid is deterministic without a client-side sort step.
    ``total`` is the count of entries in ``documents`` -- always equal
    to ``len(documents)`` for the current single-page response shape,
    surfaced as its own field so a future paginated variant can extend
    without breaking existing FE consumers.
    """

    documents: list[SourceListing] = Field(
        default_factory=list[SourceListing],
        description="One entry per distinct ingested source.",
    )
    total: int = Field(
        ...,
        description="Total number of distinct sources in this response.",
        ge=0,
    )


class IngestUrlRequest(BaseModel):
    """Request body for ``POST /api/admin/documents/url``.

    ``url`` is constrained but intentionally NOT typed as ``HttpUrl``:
    Pydantic's ``HttpUrl`` enforces TLDs which trips on intranet hosts
    (``http://docs.internal/article``) that v1's admin upload happily
    accepted. We instead validate non-empty + length-cap + parse-shape
    at the handler layer (``functions.add_url.url_fetcher.fetch_url``
    already raises on malformed URLs).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the document to fetch and index.",
    )
    ingestion_job_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        description="Correlation id surfaced in logs across the ingest pipeline.",
    )


class IngestUrlResponse(BaseModel):
    """Response shape for ``POST /api/admin/documents/url``."""

    ingestion_job_id: str = Field(
        ..., description="Correlation id for cross-log tracing."
    )
    url: str = Field(..., description="Echo of the URL that was ingested.")
    document_count: int = Field(
        ...,
        ge=0,
        description="Number of chunks written to the search index.",
    )


class UploadResponse(BaseModel):
    """Response shape for ``POST /api/admin/documents`` (multipart upload).

    The route writes the file to the source blob container and
    enqueues a single ``BatchPushQueueMessage`` so the existing
    ``batch_push`` queue consumer picks it up and runs the same
    parse / embed / push pipeline used by ``batch_start``. The
    response is the operator-facing receipt: filename echo, blob
    path for storage-explorer lookup, ``queued=True`` once the push
    envelope is on the wire, and the correlation id propagated into
    every downstream log line.
    """

    filename: str = Field(
        ..., description="Echo of the uploaded filename."
    )
    blob_path: str = Field(
        ...,
        description=(
            "Storage path the blob was written to, formatted as "
            "``<container>/<filename>``."
        ),
    )
    ingestion_job_id: str = Field(
        ..., description="Correlation id for cross-log tracing."
    )
    queued: bool = Field(
        ...,
        description=(
            "True once the push-queue message is enqueued so the "
            "``batch_push`` consumer will pick it up."
        ),
    )


class ReprocessResponse(BaseModel):
    """Response shape for ``POST /api/admin/documents/reprocess``.

    The route fans every blob in the documents container out to the
    push queue (single ``batch_start`` invocation under the hood), so
    every existing document is re-parsed + re-embedded + re-pushed
    through the same pipeline a freshly-uploaded file traverses.
    ``ingestion_job_id`` is the correlation id shared by every
    enqueued envelope (mirrors the Functions ``batch_start`` shape so
    operators can pivot between the two entry points by job id) and
    is ``None`` when the container is empty.
    """

    ingestion_job_id: str | None = Field(
        ...,
        description=(
            "Correlation id shared by every enqueued envelope, or "
            "``None`` when the container had no blobs to enqueue."
        ),
    )
    enqueued_count: int = Field(
        ...,
        ge=0,
        description="Number of push-queue envelopes written for this fan-out.",
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
    "IngestUrlRequest",
    "IngestUrlResponse",
    "ListDocumentsResponse",
    "ReprocessResponse",
    "UploadResponse",
    "WRITABLE_FIELDS",
]
