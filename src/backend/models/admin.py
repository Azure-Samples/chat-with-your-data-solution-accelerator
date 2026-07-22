"""Admin router request/response models."""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.core.agents.presets import AssistantType
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
    """Runtime-toggle subset of ``AppSettings`` (read-only view).

    The fields exposed here are exactly the settings that the admin
    PATCH endpoint mutates at runtime. Selection criteria:

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

    orchestrator_name: str = Field(
        description=(
            "Key of the active orchestrator provider (e.g. langgraph or "
            "agent_framework)."
        )
    )
    openai_temperature: float = Field(
        description="Sampling temperature applied to chat completions (higher is more random)."
    )
    openai_max_tokens: int = Field(
        description="Maximum number of tokens generated per chat completion."
    )
    search_use_semantic_search: bool = Field(
        description="Whether retrieval applies semantic ranking over the search results."
    )
    search_top_k: int = Field(
        description="Number of top search results retrieved to ground each answer."
    )
    log_level: str = Field(
        description="Application log verbosity (e.g. INFO or DEBUG)."
    )
    content_safety_enabled: bool = Field(
        description="Whether inbound and outbound content-safety screening is applied."
    )
    cwyd_agent_instructions: str = Field(
        description="Operator-editable system prompt for the primary answering agent."
    )
    ai_assistant_type: AssistantType = Field(
        description=(
            "Selected prompt preset persona (default, contract assistant, or "
            "employee assistant)."
        )
    )
    post_answering_prompt: str = Field(
        description="Optional prompt used to validate a composed answer before returning it."
    )
    post_answering_enabled: bool = Field(
        description="Whether the post-answering validation step runs after each answer."
    )
    post_answering_filter_message: str = Field(
        description=(
            "Message returned to the user when post-answering validation "
            "rejects an answer."
        )
    )


# Allow-list of writable `RuntimeConfig` fields (the mutable subset --
# `updated_at` / `updated_by` are server-set and rejected on input).
# Computed once at module import so request validation is O(1).
WRITABLE_FIELDS: frozenset[str] = frozenset(
    name
    for name in RuntimeConfig.model_fields
    if name not in {"updated_at", "updated_by"}
)


# Subset of `WRITABLE_FIELDS` whose values are operator-authored system
# prompts. PATCH funnels each non-empty value at one of these keys
# through the RAI safety classifier before persisting; the helper is
# `backend.services.admin.validate_prompt_with_rai`. New prompt-shaped
# fields auto-gate by adding their key here -- no router-layer edit.
PROMPT_FIELDS: frozenset[str] = frozenset(
    {"cwyd_agent_instructions", "post_answering_prompt"}
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

    orchestrator_name: str = Field(
        description="Key of the active orchestrator provider."
    )
    db_type: str = Field(description="Configured chat-history backend identifier.")
    index_store: str = Field(description="Configured search index backend identifier.")
    environment: str = Field(
        description="Deployment environment name (e.g. local or production)."
    )
    foundry_project_endpoint_host: str = Field(
        description="Hostname of the Foundry project endpoint in use."
    )
    gpt_deployment: str = Field(
        description="Name of the deployed chat/completion model."
    )
    embedding_deployment: str = Field(
        description="Name of the deployed embedding model."
    )
    search_enabled: bool = Field(
        description="Whether document search and retrieval is enabled."
    )
    app_insights_enabled: bool = Field(
        description="Whether Application Insights telemetry is enabled."
    )
    cors_origins: list[str] = Field(
        default_factory=list[str],
        description="Allowed CORS origins for browser clients.",
    )
    version: str = Field(description="Backend application version.")


class DeleteDocumentResponse(BaseModel):
    """Response shape for ``DELETE /api/admin/documents/{source}``."""

    deleted: int = Field(
        ...,
        description="Number of indexed chunks removed for the source.",
        ge=0,
    )
    blob_deleted: bool = Field(
        default=False,
        description=(
            "Whether the source blob was removed from the documents "
            "container (False for URL-typed sources, which have no blob)."
        ),
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
    """Response shape for ``POST /api/admin/documents/url``.

    The route downloads the URL and writes it to the documents
    container as a blob, then the same ``batch_push`` pipeline used by
    file upload indexes it (enqueued under ``DIRECT_ENQUEUE``;
    Event-Grid-driven otherwise). The response is the operator-facing
    receipt: the URL echo, the derived blob filename + path, ``queued``
    reflecting whether the backend enqueued the push envelope, and the
    correlation id propagated into every downstream log line.
    """

    url: str = Field(..., description="Echo of the URL that was ingested.")
    filename: str = Field(
        ...,
        description="Derived blob filename the URL content was stored as.",
    )
    blob_path: str = Field(
        ...,
        description=(
            "Storage path the blob was written to, formatted as "
            "``<container>/<filename>``."
        ),
    )
    ingestion_job_id: str = Field(
        ...,
        description=(
            "Correlation id stamped on every downstream log line. Under "
            "``DIRECT_ENQUEUE`` it is also the id carried by the enqueued "
            "``BatchPushQueueMessage``; under ``EVENT_GRID`` nothing is "
            "enqueued (``queued`` is False), so the id is informational -- "
            "a log-tracing handle with no enqueued push job to correlate to."
        ),
    )
    queued: bool = Field(
        ...,
        description=(
            "Whether the backend enqueued the push envelope (False when "
            "the Event Grid trigger drives ingestion instead)."
        ),
    )


class UploadResponse(BaseModel):
    """Response shape for ``POST /api/admin/documents`` (multipart upload).

    The route writes the file to the source blob container. When the
    deploy's ingestion trigger is ``DIRECT_ENQUEUE`` it then enqueues a
    single ``BatchPushQueueMessage`` so the existing ``batch_push``
    queue consumer picks it up and runs the same parse / embed / push
    pipeline used by ``batch_start``; when the trigger is
    ``EVENT_GRID`` a storage Event Grid subscription drives that step
    instead, so the route writes the blob only. The response is the
    operator-facing receipt: filename echo, blob path for
    storage-explorer lookup, ``queued`` reflecting whether the backend
    enqueued the push envelope, and the correlation id propagated into
    every downstream log line.
    """

    filename: str = Field(..., description="Echo of the uploaded filename.")
    blob_path: str = Field(
        ...,
        description=(
            "Storage path the blob was written to, formatted as "
            "``<container>/<filename>``."
        ),
    )
    ingestion_job_id: str = Field(
        ...,
        description=(
            "Correlation id stamped on every downstream log line. Under "
            "``DIRECT_ENQUEUE`` it is also the id carried by the enqueued "
            "``BatchPushQueueMessage``; under ``EVENT_GRID`` nothing is "
            "enqueued (``queued`` is False), so the id is informational -- "
            "a log-tracing handle with no enqueued push job to correlate to."
        ),
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
    """Merged effective view of `AdminConfig`.

    Combines the env-default snapshot returned by
    ``GET /api/admin/config`` with the persisted `RuntimeConfig`
    overrides loaded into ``app.state.runtime_overrides`` by the
    lifespan + PATCH writeback channel. Each field on
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

    values: AdminConfig = Field(description="Resolved effective configuration values.")
    sources: dict[str, ConfigSource] = Field(
        description=(
            "Per-field provenance: env when tracking the deployed default, "
            "override when held by a persisted runtime override."
        )
    )
    assistant_type_presets: dict[str, str] = Field(
        description=(
            "Read-only map of assistant type to persona prompt body that the "
            "frontend dropdown loads into the answering-prompt field on "
            "selection. Reference data only, so it carries no provenance entry."
        )
    )
    updated_at: str | None = Field(
        default=None,
        description=(
            "ISO-8601 timestamp of the last override write, or null when no "
            "override row exists."
        ),
    )
    updated_by: str | None = Field(
        default=None,
        description=(
            "User id of the last override author, or null when no override row "
            "exists."
        ),
    )


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
    "PROMPT_FIELDS",
    "ReprocessResponse",
    "UploadResponse",
    "WRITABLE_FIELDS",
]
