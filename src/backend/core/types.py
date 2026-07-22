"""Shared Pydantic types used by providers and pipelines.

Keep this file focused on **value types** (request/response shapes,
domain objects) -- not behavior. Provider classes live under
`providers/`. Cross-cutting helpers live under `shared/tools/`.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.agents.presets import AssistantType


class AadScope(StrEnum):
    """Closed-set AAD token-scope discriminator for UAMI/AAD auth (Hard Rule #11).

    Single argument to ``AsyncTokenCredential.get_token(...)`` at every
    Azure SDK boundary in v2 -- Hard Rule #2 bans Key Vault and
    subscription keys, so every data-plane call goes through one of
    these scopes. ``COGNITIVE_SERVICES`` covers the unified Foundry AI
    Services account (Document Intelligence, Content Understanding,
    OpenAI, Speech) per ``infra/main.bicep``. ``POSTGRES_FLEX``
    covers Postgres Flexible Server's Entra-only auth. ``SEARCH``
    covers the Azure AI Search data plane -- including the Foundry IQ
    Knowledge Base managed MCP endpoint, which authenticates the
    caller-supplied bearer against the search service's RBAC.

    ``StrEnum`` subclassing keeps the wire-shape contract intact: SDK
    methods declared with ``*scopes: str`` accept the enum member
    transparently because each member IS a ``str``.
    """

    COGNITIVE_SERVICES = "https://cognitiveservices.azure.com/.default"
    POSTGRES_FLEX = "https://ossrdbms-aad.database.windows.net/.default"
    SEARCH = "https://search.azure.com/.default"


class ChatRole(StrEnum):
    """Closed-set role discriminator for chat messages (Hard Rule #11).

    Four members mirror the OpenAI / AzureOpenAI chat message contract.
    Used as the type for `ChatMessage.role` and `MessageRecord.role`;
    dispatched on at runtime in `pipelines/chat.py::_latest_user_text`
    and `orchestrators/langgraph.py::_latest_user_text` via
    `is ChatRole.USER` identity comparison. `StrEnum` subclassing keeps
    every external producer that passes a bare string
    (`ChatMessage(role="user", ...)`, `cosmosdb._read_item`'s
    `role=item.get("role", "user")`) working unchanged -- Pydantic
    coerces the string to the matching enum member, and JSON
    serialization emits the raw value so the wire shape is preserved.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class OrchestratorChannel(StrEnum):
    """SSE channels exposed by orchestrators on the reasoning feed.

    Defined as a `StrEnum` (Python 3.11+) per Hard Rule #11: any
    closed-set string discriminator must be an enum so the wire
    contract is centrally enumerable. Subclassing `str` keeps every
    existing producer that passes a bare string to
    `OrchestratorEvent(channel="answer", ...)` working unchanged --
    Pydantic coerces the string to the matching enum member, and
    `event.channel == "answer"` keeps holding because `StrEnum`
    members are strings. New producer code MUST use the enum members
    (`OrchestratorChannel.ANSWER` etc.) so the closed set stays
    grep-able. Frontend renders `REASONING` events in a collapsible
    panel and `ANSWER` events as the final response (per
    v2-workflow.instructions.md).

    Defined here -- not in `providers/orchestrators/` -- so providers
    like `FoundryIQ.reason()` can yield events without reaching across
    packages.
    """

    REASONING = "reasoning"
    TOOL = "tool"
    ANSWER = "answer"
    CITATION = "citation"
    ERROR = "error"


class ChatMessage(BaseModel):
    """One turn in a chat conversation.

    `metadata` carries provider-agnostic extras that travel with the
    turn into storage -- e.g. the citations surfaced alongside an
    assistant answer, so a reloaded conversation rehydrates them
    without re-running retrieval. Mirrors `MessageRecord.metadata`
    (the persisted read-side shape) and defaults to an empty dict so
    every existing producer that builds `ChatMessage(role=...,
    content=...)` is unaffected.
    """

    role: ChatRole = Field(
        description="Author role of the turn (system, user, assistant, or tool)."
    )
    content: str = Field(description="Text content of the turn.")
    name: str | None = Field(
        default=None, description="Optional author name for the turn."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Provider-agnostic extras that travel with the turn into storage "
            "(e.g. citations surfaced alongside an assistant answer)."
        ),
    )


class ChatChunk(BaseModel):
    """One streamed delta from a chat completion."""

    content: str = ""
    finish_reason: str | None = None


class EmbeddingResult(BaseModel):
    """Result of an embedding call. One vector per input."""

    vectors: list[list[float]] = Field(default_factory=list[list[float]])
    model: str = ""

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


class Chunk(BaseModel):
    """One parsed text fragment ready for embedding + indexing.

    Returned by `BaseParser.parse(...)` and consumed by the batch_push
    handler. Carried as the unit of work between the parser, the
    embedder, and the search writer -- no chunker primitive sits in
    between.

    Frozen + `extra="forbid"` so the ingestion pipeline cannot
    silently smuggle provider-specific fields through `metadata`
    siblings -- anything provider-specific (page index, bounding box,
    section heading, source URL) goes inside the `metadata` dict
    where consumers can opt in.

    `id` is a deterministic chunk identifier built via
    `BaseParser.make_chunk_id(source, index)` (a SHA-256 hash of the
    readable `f"{source}__{index}"`) so re-indexing the same source
    produces stable, Search-safe document keys. `source` is the
    originating filename or URL. `index` is the chunk's position
    within `source` (0-based).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    content: str
    source: str = ""
    index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestratorEvent(BaseModel):
    """Single event on the SSE reasoning feed.

    Shape is locked here so any producer (LLM provider's `reason()`,
    every concrete orchestrator, tool runners) emits the same wire
    format. Frontend renders `reasoning` events in a collapsible panel
    and `answer` events as the final response (per
    v2-workflow.instructions.md).
    """

    channel: OrchestratorChannel
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """One source citation surfaced alongside an answer.

    `id` is the source document/chunk id (provider-specific). `url` is
    a renderable link (blob SAS, URL of an external page, ...). `score`
    is the search relevance, normalized 0..1 where the provider can
    expose one. Frontend dedupes by `id`.
    """

    id: str = Field(
        description=(
            "Source document or chunk id (provider-specific); the frontend "
            "dedupes citations by this value."
        )
    )
    title: str = Field(default="", description="Display title of the source.")
    url: str = Field(
        default="",
        description="Renderable link to the source (blob SAS URL, external page URL).",
    )
    snippet: str = Field(
        default="",
        description="Short excerpt of the source text supporting the answer.",
    )
    score: float | None = Field(
        default=None,
        description=(
            "Search relevance normalized 0..1 when the provider exposes one; "
            "null otherwise."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific extra fields."
    )


class SearchResult(BaseModel):
    """A single hit returned by a `BaseSearch.search()` call.

    The orchestrator / RAG pipeline turns these into `Citation`s and
    folds the `content` into the prompt context. Kept minimal: provider
    -specific extras land in `metadata`.
    """

    id: str
    content: str
    title: str = ""
    url: str = ""
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchDocument(BaseModel):
    """A document written to the search index by an ingestion handler.

    Wire shape produced by the Functions ingestion pipeline
    (``batch_push``, ``add_url``, ``search_skill``) and consumed by
    :func:`backend.core.providers.search.writer.push_documents`, which
    calls ``model_dump()`` at the Azure Search SDK boundary. Field
    names mirror the read-side mapping in
    :class:`backend.core.providers.search.azure_search.AzureSearch._to_result`
    + its ``_DEFAULT_SELECT_FIELDS`` tuple so an in-place schema
    upgrade does not require a reindex.

    Frozen + ``extra="forbid"`` so each ingestion path cannot smuggle
    provider-specific fields through the wire shape -- anything
    blueprint-specific (page index, bounding box, blob SAS URL,
    source HTML title) goes elsewhere (currently embedded in
    ``title`` / ``content``; a future ``metadata`` field would be
    added here AND mirrored on the read side).

    YAGNI breadcrumb: ``url`` is intentionally omitted today --
    ``batch_push`` / ``add_url`` do not yet produce a SAS URL or
    source URL field. When the field arrives, add it here AND to
    ``_DEFAULT_SELECT_FIELDS`` in ``azure_search.py`` AND to
    :class:`SearchResult` so read + write stay in lockstep.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    content: str
    title: str = ""
    content_vector: list[float] = Field(default_factory=list[float])


class Conversation(BaseModel):
    """One stored chat conversation owned by a user.

    Returned by `BaseDatabaseClient` chat-history methods. `created_at`
    / `updated_at` are ISO-8601 strings (provider-formatted) so the
    wire shape is stable across Cosmos DB and PostgreSQL.
    """

    id: str = Field(description="Unique conversation id.")
    user_id: str = Field(description="Id of the user who owns the conversation.")
    title: str = Field(default="", description="Display title of the conversation.")
    created_at: str = Field(
        default="", description="ISO-8601 timestamp when the conversation was created."
    )
    updated_at: str = Field(
        default="", description="ISO-8601 timestamp of the most recent update."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific extra fields."
    )


class MessageRecord(BaseModel):
    """One stored message inside a `Conversation`.

    Wraps `ChatMessage` with persistence fields (id, conversation_id,
    timestamp, optional feedback). Frontend renders `feedback` as a
    thumbs-up/down indicator.
    """

    id: str = Field(description="Unique message id.")
    conversation_id: str = Field(
        description="Id of the conversation this message belongs to."
    )
    role: ChatRole = Field(description="Author role of the message.")
    content: str = Field(description="Message text.")
    created_at: str = Field(
        default="", description="ISO-8601 timestamp when the message was stored."
    )
    feedback: str | None = Field(
        default=None,
        description=(
            "User feedback marker rendered as a thumbs-up/down indicator; null "
            "when no feedback was given."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific extra fields."
    )


class RuntimeConfig(BaseModel):
    """Persisted runtime overrides for the admin-mutable subset of
    `AppSettings`.

    Mirrors the runtime-toggle fields exposed read-only by
    `AdminConfig` (orchestrator key, OpenAI
    temperature/max_tokens, search semantic-toggle/top_k, log_level,
    content_safety_enabled). Persisted via
    `BaseDatabaseClient.upsert_runtime_config(...)` and
    read via `get_runtime_config()`. The CosmosDB row
    pins to the synthetic `_system` partition (mirrors the
    `AGENT` row); the Postgres row uses a singleton
    `id INT PRIMARY KEY DEFAULT 1` row with `INSERT ... ON CONFLICT`
    upsert semantics.

    All mutable fields are `T | None = None` so the persisted shape
    can distinguish 'explicitly overridden' from 'not overridden' --
    required for booleans like `search_use_semantic_search` or
    `content_safety_enabled` where `False` is a legitimate override
    value distinct from 'fall through to env default'.
    The RFC 7396 merge semantics rely on this
    distinction: an absent JSON key leaves the override alone, an
    explicit `null` clears the override, an explicit value sets it.

    `cwyd_agent_instructions` is the operator-editable system prompt
    for the primary `CWYD_AGENT`. When `None`, the agents provider
    falls through to the built-in instructions on the
    `AgentDefinition` singleton; when set, the provider applies the
    override at agent-creation time.

    `ai_assistant_type` records which prompt preset the operator
    selected (default / contract assistant / employee assistant, ADR
    0030). It is UI / provenance state -- the prompt that actually
    flows to the agent is `cwyd_agent_instructions` (the frontend
    loads the selected preset body into it). `None` falls through to
    the default type.

    `post_answering_prompt`, `post_answering_enabled`, and
    `post_answering_filter_message` configure the optional
    `PostPromptValidator` wired into the chat pipeline. When
    `post_answering_enabled` is `True` and `post_answering_prompt` is
    non-empty, the chat pipeline runs the validator after the answer
    is composed; on a FALSE verdict, the user receives
    `post_answering_filter_message` (or a built-in default when the
    override is empty). All three default to `None` so the validator
    stays off until an operator explicitly enables it.

    `updated_at` is an ISO-8601 string for the same reason
    `Conversation.updated_at` is -- the wire shape stays uniform
    across providers (Cosmos JSON, Postgres). `updated_by` carries
    the admin caller's user id (from `get_user_id` / `UserIdDep` in
    `backend.dependencies`) so an audit query can answer 'who flipped
    temperature to 0.7?'.
    """

    orchestrator_name: str | None = Field(
        default=None,
        description=(
            "Override for the active orchestrator provider key; null falls "
            "through to the deployed default."
        ),
    )
    openai_temperature: float | None = Field(
        default=None,
        description=(
            "Override for the chat sampling temperature; null falls through to "
            "the deployed default."
        ),
    )
    openai_max_tokens: int | None = Field(
        default=None,
        description=(
            "Override for the maximum tokens per completion; null falls through "
            "to the deployed default."
        ),
    )
    search_use_semantic_search: bool | None = Field(
        default=None,
        description=(
            "Override for the semantic-search toggle; null falls through to the "
            "deployed default."
        ),
    )
    search_top_k: int | None = Field(
        default=None,
        description=(
            "Override for the number of retrieved search results; null falls "
            "through to the deployed default."
        ),
    )
    log_level: str | None = Field(
        default=None,
        description=(
            "Override for the log verbosity; null falls through to the deployed "
            "default."
        ),
    )
    content_safety_enabled: bool | None = Field(
        default=None,
        description=(
            "Override for the content-safety toggle; null falls through to the "
            "deployed default."
        ),
    )
    cwyd_agent_instructions: str | None = Field(
        default=None,
        description=(
            "Override for the primary agent's system prompt; null falls through "
            "to the built-in instructions."
        ),
    )
    ai_assistant_type: AssistantType | None = Field(
        default=None,
        description=(
            "Override for the selected prompt preset persona; null falls "
            "through to the default type."
        ),
    )
    post_answering_prompt: str | None = Field(
        default=None,
        description="Override for the post-answering validation prompt; null leaves it unset.",
    )
    post_answering_enabled: bool | None = Field(
        default=None,
        description="Override for the post-answering validation toggle; null leaves it unset.",
    )
    post_answering_filter_message: str | None = Field(
        default=None,
        description=(
            "Override for the message shown when post-answering validation "
            "rejects an answer; null leaves it unset."
        ),
    )
    updated_at: str = Field(
        default="",
        description="ISO-8601 timestamp of the last override write; empty when never written.",
    )
    updated_by: str = Field(
        default="",
        description="User id of the last override author; empty when never written.",
    )


class AdminAuditEntry(BaseModel):
    """Append-only audit row for admin config mutations.

    Persisted by `BaseDatabaseClient.write_admin_audit` after every
    successful `PATCH /api/admin/config`. The wire
    shape is uniform across providers (Cosmos: one item with
    `type=admin_audit` in the `_system` partition; Postgres: one
    row in `admin_audit` table) and captures the four answers
    an operator forensic query needs:

    * **who** -- `actor` is the admin user id (Entra object id)
      surfaced by `get_user_id` / `UserIdDep` in `backend.dependencies`.
    * **what** -- `action` is a short verb (today: `"patch_config"`)
      that lets a future audit query filter by operation kind.
    * **before** / **after** -- the `RuntimeConfig` snapshots the
      PATCH route observed before applying the merge and the merged
      shape it persisted. `before is None` on the first-ever PATCH
      (no prior override row) -- distinct from
      `RuntimeConfig()` (every override cleared), see
      `test_write_admin_audit_serializes_before_as_none_for_first_patch`.
    * **when** -- the storage layer assigns `created_at` (ISO-8601
      UTC) on persist alongside the row id (mirrors `add_message`),
      so the router fires-and-forgets without minting timestamps
      itself.

    The router builds the entry with `actor / action / before /
    after` and the storage layer fills `id` + `created_at` -- the
    return type of `write_admin_audit` is `None` because the
    audit log is fire-and-forget; no caller needs the row id back.
    """

    actor: str
    action: str
    before: RuntimeConfig | None = None
    after: RuntimeConfig


__all__ = [
    "AadScope",
    "AdminAuditEntry",
    "ChatChunk",
    "ChatMessage",
    "ChatRole",
    "Citation",
    "Conversation",
    "EmbeddingResult",
    "MessageRecord",
    "OrchestratorChannel",
    "OrchestratorEvent",
    "RuntimeConfig",
    "SearchDocument",
    "SearchResult",
]
