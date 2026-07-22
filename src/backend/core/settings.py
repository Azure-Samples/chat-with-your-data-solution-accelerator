"""Typed runtime configuration for the v2 stack.

`AppSettings` composes ~9 small `BaseSettings` models, one per Azure
subsystem, that read **only** the `AZURE_*` env vars emitted by
`infra/main.bicep` outputs. The orchestrator namespace uses the
runtime-tunable `CWYD_` prefix because it is not infra-pinned.

Design rules (binding):

* No Key Vault. No secrets in fields. Every credential is acquired at
  runtime via Managed Identity through the `providers/credentials/`
  registry domain.
* Conditional Bicep outputs (cosmos / postgres / search / monitoring /
  vnet) default to empty strings here, mirroring the Bicep convention
  that "off" emits `''`. A `model_validator` on `DatabaseSettings`
  enforces that the side matching `AZURE_DB_TYPE` is populated.
* `get_settings()` is a `@lru_cache(maxsize=1)` singleton, **not** a
  module-level instance, so tests can call `get_settings.cache_clear()`
  between env-var permutations and FastAPI can `Depends(get_settings)`.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any, cast

import json

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Cross-cutting enums


class Environment(StrEnum):
    """Runtime mode discriminator for `AppSettings.environment`.

    Members:
        LOCAL: developer machine; the default for a clean checkout.
        PRODUCTION: cloud deployment, set via `AZURE_ENVIRONMENT` by
            `infra/main.bicep`.
    """

    LOCAL = "local"
    PRODUCTION = "production"


class DbType(StrEnum):
    """Registry key for the chat-history database backend.

    Values are the registry keys passed to
    `databases_registry.registry.get(...)`. `StrEnum` subclasses `str`
    so dict lookups and JSON serialization round-trip unchanged; the
    enum exists to satisfy Hard Rule #11 at the comparison sites.

    Members:
        COSMOSDB: Azure Cosmos DB for NoSQL.
        POSTGRESQL: Azure Database for PostgreSQL Flexible Server.
    """

    COSMOSDB = "cosmosdb"
    POSTGRESQL = "postgresql"


class IndexStore(StrEnum):
    """Registry key for the vector index store.

    Values are the registry keys passed to
    `search_registry.registry.get(...)`. `StrEnum` subclasses `str`
    so dict lookups and JSON serialization round-trip unchanged; the
    enum exists to satisfy Hard Rule #11 at the comparison sites.

    Members:
        AZURE_SEARCH: Azure AI Search (index provisioned by Bicep).
        PGVECTOR: `pgvector` extension on the postgres backend
            (`documents` table provisioned by `PgVector.ensure_schema`).
    """

    AZURE_SEARCH = "AzureSearch"
    PGVECTOR = "pgvector"


class OrchestratorName(StrEnum):
    """Registry key for the chat orchestrator.

    Values are the registry keys passed to
    `orchestrators_registry.registry.get(...)`. `StrEnum` subclasses
    `str` so dict lookups and JSON serialization round-trip unchanged;
    the enum exists to satisfy Hard Rule #11 at the comparison sites.

    Members:
        LANGGRAPH: app-owned LangGraph RAG pipeline; works on either
            index store.
        AGENT_FRAMEWORK: Foundry agent delegation grounded by a Foundry
            IQ Knowledge Base over the Azure AI Search index.
    """

    LANGGRAPH = "langgraph"
    AGENT_FRAMEWORK = "agent_framework"


class IngestionTrigger(StrEnum):
    """How a written source blob gets picked up for indexing.

    Closed-set env discriminator fully owned by the codebase (no
    registry dispatch), so a hard `StrEnum` with no `str` arm per
    Hard Rule #11.

    Members:
        DIRECT_ENQUEUE: the backend admin upload path enqueues a push
            message to `doc_processing_queue` itself. The only trigger
            available for local dev and any deploy without a storage
            Event Grid subscription; the default.
        EVENT_GRID: a storage Event Grid subscription fans
            `BlobCreated` to the `blob-events` queue, which the
            Functions `blob_event` queue trigger translates into a push
            message. The backend writes the blob only and does not
            enqueue, so a blob never double-ingests.
    """

    DIRECT_ENQUEUE = "direct_enqueue"
    EVENT_GRID = "event_grid"


# Per-subsystem settings


class IdentitySettings(BaseSettings):
    """User-assigned managed identity + tenant info.

    Reads: AZURE_TENANT_ID, AZURE_UAMI_CLIENT_ID,
    AZURE_UAMI_PRINCIPAL_ID, AZURE_UAMI_RESOURCE_ID.
    """

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    tenant_id: str = ""
    uami_client_id: str = ""
    uami_principal_id: str = ""
    uami_resource_id: str = ""


class FoundrySettings(BaseSettings):
    """Foundry / AI Services substrate.

    Reads: AZURE_AI_SERVICES_ENDPOINT, AZURE_AI_PROJECT_ENDPOINT,
    AZURE_AI_SERVICE_LOCATION, AZURE_AI_AGENT_API_VERSION.
    """

    model_config = SettingsConfigDict(env_prefix="AZURE_AI_", extra="ignore")

    services_endpoint: str = ""
    project_endpoint: str = ""
    service_location: str = ""
    agent_api_version: str = ""


class OpenAISettings(BaseSettings):
    """Azure OpenAI deployments routed through the Foundry account."""

    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_", extra="ignore")

    api_version: str = ""
    gpt_deployment: str = ""
    embedding_deployment: str = ""
    embedding_dimensions: int = 1536
    temperature: float = 0.0
    max_tokens: int = 1000


class DatabaseSettings(BaseSettings):
    """Selects the chat-history backend AND the vector index store.

    `db_type` is the registry key resolved via
    `databases_registry.registry.get(...)`; `index_store` selects the
    vector search handler via `search_registry.registry.get(...)`.

    Note: the `databases` provider domain owns chat-history CRUD plus
    any future DB-backed concerns (vector-store metadata, config
    storage). There is intentionally no separate `chat_history`
    provider domain -- a single client per backend (cosmosdb /
    postgresql) keeps the connection pool unified.
    """

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    db_type: DbType | str = DbType.COSMOSDB
    index_store: IndexStore | str = IndexStore.AZURE_SEARCH

    # cosmosdb mode (empty in postgresql mode)
    cosmos_endpoint: str = ""
    cosmos_account_name: str = ""
    cosmos_database_name: str = "cwyd"
    cosmos_container_name: str = "conversations"

    # postgresql mode (empty in cosmosdb mode)
    postgres_endpoint: str = ""  # full libpq URI from AZURE_POSTGRES_ENDPOINT
    postgres_host: str = ""
    postgres_name: str = ""
    postgres_admin_principal_name: str = ""

    @model_validator(mode="after")
    def _enforce_mode_consistency(self) -> "DatabaseSettings":
        # Pydantic config-consistency validator. Not provider dispatch (no
        # class instantiation, no behavior branch); registry callers always
        # go through `databases_registry.registry.get(db_type)` /
        # `search_registry.registry.get(index_store)` per Hard Rule #4.
        if self.db_type == DbType.COSMOSDB:
            if not self.cosmos_endpoint:
                raise ValueError(
                    "AZURE_DB_TYPE=cosmosdb requires AZURE_COSMOS_ENDPOINT to be set."
                )
            if self.index_store != IndexStore.AZURE_SEARCH:
                raise ValueError(
                    "AZURE_DB_TYPE=cosmosdb requires AZURE_INDEX_STORE=AzureSearch."
                )
        elif self.db_type == DbType.POSTGRESQL:
            if not self.postgres_endpoint:
                raise ValueError(
                    "AZURE_DB_TYPE=postgresql requires AZURE_POSTGRES_ENDPOINT to be set."
                )
            if self.index_store != IndexStore.PGVECTOR:
                raise ValueError(
                    "AZURE_DB_TYPE=postgresql requires AZURE_INDEX_STORE=pgvector."
                )
        # Third-party `db_type` (str arm of `DbType | str` /
        # `IndexStore | str` per Hard Rule #11 registry-driven carve-out).
        # First-party env-var coupling does not apply: the plugin owns its
        # own env-var validation at provider construction; the
        # `databases_registry.registry.get(...)` / `search_registry.registry
        # .get(...)` boundary is the dispatch-time guard.
        return self


class SearchSettings(BaseSettings):
    """Azure AI Search (cosmosdb mode only; empty otherwise)."""

    model_config = SettingsConfigDict(env_prefix="AZURE_AI_SEARCH_", extra="ignore")

    endpoint: str = ""
    name: str = ""
    index: str = "cwyd-index"
    use_semantic_search: bool = True
    top_k: int = 5

    # Foundry IQ Knowledge Base over `index`: a `searchIndex` knowledge source
    # wraps the existing index, and the agent_framework orchestrator grounds on
    # the KB. `knowledge_base_api_version` pins the KB REST API version so an
    # operator can bump it via env var without a code change.
    knowledge_base_name: str = "cwyd-kb"
    knowledge_source_name: str = "cwyd-index-ks"
    knowledge_base_api_version: str = "2025-11-01-preview"

    # Foundry project connection (category CognitiveSearch) that the KB MCP
    # tool references for server-side retrieval; surfaced from infra as
    # `AZURE_AI_SEARCH_CONNECTION_NAME`. Empty in postgresql mode (no KB).
    connection_name: str = ""


class StorageSettings(BaseSettings):
    """Shared storage account (RAG documents + indexing queues)."""

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    storage_account_name: str = ""
    storage_blob_endpoint: str = ""
    documents_container: str = ""
    doc_processing_queue: str = ""
    ingestion_trigger: IngestionTrigger = IngestionTrigger.DIRECT_ENQUEUE


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry / App Insights wiring (optional)."""

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    app_insights_connection_string: str = ""
    log_level: str = "INFO"


class NetworkSettings(BaseSettings):
    """Public URLs and (optional) VNet metadata."""

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    backend_url: str = ""
    frontend_url: str = ""
    function_app_url: str = ""
    function_app_name: str = ""
    vnet_name: str = ""
    vnet_resource_id: str = ""
    bastion_name: str = ""

    # CORS origins for the backend FastAPI CORSMiddleware. Read from the
    # bare `BACKEND_CORS_ORIGINS` env var (no `AZURE_` prefix) so it
    # matches the v1 / Bicep convention and what every operator's
    # `.env` already uses. The validator accepts:
    #   - a comma-separated string ("http://a, http://b")  -- env-var shape
    #   - a JSON-style list (`["http://a","http://b"]`)     -- compose YAML
    #   - an already-parsed Python list (programmatic tests)
    # Empty string -> empty list (CORSMiddleware then allows nothing).
    #
    # `NoDecode` keeps pydantic-settings from auto-JSON-decoding the env
    # value before our `mode="before"` validator runs; without it the
    # comma-separated form raises `SettingsError` because it's not valid
    # JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "cors_origins"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, raw: object) -> list[str]:
        if raw is None or raw == "":
            return []
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                return []
            # Tolerate JSON-list shape so docker-compose can pass either
            # form without surprising the operator.
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    parsed_list = cast(list[Any], parsed)
                    return [
                        str(item).strip() for item in parsed_list if str(item).strip()
                    ]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(raw, (list, tuple)):
            raw_seq = cast("list[Any] | tuple[Any, ...]", raw)
            return [str(item).strip() for item in raw_seq if str(item).strip()]
        raise ValueError(
            "BACKEND_CORS_ORIGINS must be a comma-separated string or list."
        )


class OrchestratorSettings(BaseSettings):
    """Runtime-tunable orchestrator selection (registry key).

    Distinct namespace (`CWYD_`) because the orchestrator is **not** an
    infra-pinned value -- the admin UI and tests need to flip it
    without redeploying Bicep.

    Per ADR 0008 (lazy-foundry-agent-bootstrap), the Foundry agent
    identity is not settings-driven -- the `agent_framework`
    orchestrator must call the registry-backed `agents` provider's
    `get_or_create_agent(CWYD_AGENT, ...)` on first request and let it
    persist the resolved id in the chat-history database (Cosmos in
    cosmosdb-mode, Postgres in postgresql-mode). Restoring an
    `agent_id` field here would re-introduce dead-config drift.
    """

    model_config = SettingsConfigDict(env_prefix="CWYD_ORCHESTRATOR_", extra="ignore")

    # `OrchestratorName | str` widening per Hard Rule #11 registry-driven
    # carve-out: the first-party closed set is the `OrchestratorName`
    # StrEnum, but the `str` arm admits any third-party orchestrator key
    # registered against `cwyd.providers.orchestrators` via
    # `backend.core.discovery.load_entry_points`. Validation moves to the
    # registry boundary (`orchestrators_registry.registry.get(...)`).
    #
    # Default is `AGENT_FRAMEWORK` (ADR 0021): Foundry agent delegation
    # grounded by a Foundry IQ Knowledge Base over the Azure AI Search
    # index. That pairing requires the `AzureSearch` index store, so
    # pgvector deployments must override to `LANGGRAPH`; selecting
    # `agent_framework` in pgvector mode is rejected at request time with
    # a `ConfigResolutionError` (HTTP 409) per ADR 0022 -- never a silent
    # fallback.
    name: OrchestratorName | str = OrchestratorName.AGENT_FRAMEWORK


class ContentSafetySettings(BaseSettings):
    """Azure AI Content Safety guardrail.

    Reads: AZURE_CONTENT_SAFETY_ENDPOINT, AZURE_CONTENT_SAFETY_ENABLED,
    AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD.

    `endpoint` is the regional Cognitive Services endpoint of the
    Content Safety account (e.g.
    ``https://cs-cwyd001.cognitiveservices.azure.com/``). When empty
    the lifespan wiring leaves ``app.state.content_safety_client`` as
    ``None`` and `get_content_safety_guard` returns ``None`` so the
    chat pipeline runs unguarded -- a missing endpoint disables the
    guard even when `enabled` is True.

    `enabled` is the operator switch and defaults to True
    (secure-by-default). Both `enabled=True` AND a non-empty `endpoint`
    are required to build the client at lifespan start; either alone is
    treated as "off" by the wiring layer (no guard injected, no
    exception raised), so the default is inert until an endpoint is
    configured.

    `severity_threshold` is the inclusive lower bound at which Content
    Safety verdicts trip. Azure reports severity 0/2/4/6 (0 = safe,
    2 = low, 4 = medium, 6 = high); the default 4 matches the v1
    `enable_content_safety: true` behavior. The validation ceiling of
    7 leaves room for an operator to set the guard effectively-off
    (severity > 6 is unreachable) without rejecting the value at
    settings load time.

    No subscription-key field: the lifespan wiring acquires a token
    via the `credentials` provider (UAMI -> AAD bearer), per Hard
    Rule #4 (no Key Vault, no stored secrets).
    """

    model_config = SettingsConfigDict(
        env_prefix="AZURE_CONTENT_SAFETY_", extra="ignore"
    )

    endpoint: str = ""
    enabled: bool = True
    severity_threshold: int = Field(default=4, ge=0, le=7)


class SpeechSettings(BaseSettings):
    """Azure Speech Service for browser-side speech-to-text.

    Reads: AZURE_SPEECH_SERVICE_NAME, AZURE_SPEECH_SERVICE_REGION,
    AZURE_SPEECH_ACCOUNT_RESOURCE_ID, AZURE_SPEECH_RECOGNIZER_LANGUAGES.

    The backend never streams audio: the `/api/speech` router mints a
    short-lived (10-min) Speech auth token via AAD (UAMI bearer for
    `https://cognitiveservices.azure.com/.default`) and returns it to
    the browser, which talks to Azure Speech directly via the
    `microsoft-cognitiveservices-speech-sdk`. No subscription key is
    stored anywhere (Hard Rule #2 -- AAD/UAMI only).

    `account_resource_id` is the full ARM resource id of the Speech
    account; it goes in the `x-ms-cognitiveservices-resource-id`
    header of the AAD-bearer token-mint request and lets Azure Speech
    bill / audit per-account when shared with multi-tenant
    subscription scopes.

    `recognizer_languages` is stored as the raw comma-separated string
    so env-var parity with the Bicep output stays trivial; the router
    splits on consumption (one place, one rule).
    """

    model_config = SettingsConfigDict(env_prefix="AZURE_SPEECH_", extra="ignore")

    service_name: str = ""
    service_region: str = ""
    account_resource_id: str = ""
    recognizer_languages: str = "en-US,fr-FR,de-DE,it-IT"


class DocumentIntelligenceSettings(BaseSettings):
    """Azure Document Intelligence (layout/OCR) for ingestion parsers.

    Reads: `AZURE_DOCUMENT_INTELLIGENCE_API_VERSION`,
    `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID`.

    The endpoint is intentionally NOT a field on this submodel. Per
    `infra/main.bicep` the unified AI Services account (`kind=
    AIServices`, `allowProjectManagement=true`) exposes Document
    Intelligence at `{foundry.services_endpoint}documentintelligence/`
    alongside agents, chat, and speech on the same SKU. Parsers derive
    the endpoint from `FoundrySettings.services_endpoint` at
    construction time, so a single operator env var
    (`AZURE_AI_SERVICES_ENDPOINT`) drives every Foundry data plane.

    Auth: UAMI bearer for
    `https://cognitiveservices.azure.com/.default` (Hard Rule #2 -- no
    keys, no Key Vault). RBAC: `Cognitive Services User` role on the
    unified AI Services account, granted to the UAMI in
    `infra/main.bicep`.

    `api_version` and `model_id` are operator-pinnable because GA cuts
    of `azure-ai-documentintelligence` occasionally change default
    behavior; the binding must be auditable from env vars alone, not
    buried in the SDK's package default.
    """

    model_config = SettingsConfigDict(
        env_prefix="AZURE_DOCUMENT_INTELLIGENCE_", extra="ignore"
    )

    api_version: str = "2024-11-30"
    model_id: str = "prebuilt-layout"


# Root settings


class AppSettings(BaseSettings):
    """Root configuration consumed by backend, functions, and pipelines."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    solution_suffix: str = ""
    resource_group: str = ""
    location: str = ""
    ai_service_location: str = ""

    # Runtime mode. `local` is the default so a clean checkout / dev run
    # boots without surprises. Production deployments set
    # `AZURE_ENVIRONMENT=production` via `infra/main.bicep` on the
    # backend Container App (and Function App) env-vars. The value is a
    # status-report field surfaced by `GET /api/admin/status`; Stable
    # Core code that reads the runtime mode must use this field -- never
    # sniff `os.getenv` ad-hoc -- so the value is type-checked at boot
    # and centrally testable.
    environment: Environment = Environment.LOCAL

    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    foundry: FoundrySettings = Field(default_factory=FoundrySettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    speech: SpeechSettings = Field(default_factory=SpeechSettings)
    content_safety: ContentSafetySettings = Field(default_factory=ContentSafetySettings)
    document_intelligence: DocumentIntelligenceSettings = Field(
        default_factory=DocumentIntelligenceSettings
    )


# Cached accessor (FastAPI Depends-friendly)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the process-wide `AppSettings` singleton.

    Tests should call `get_settings.cache_clear()` between env-var
    permutations.
    """
    return AppSettings()


__all__ = [
    "AppSettings",
    "ContentSafetySettings",
    "DatabaseSettings",
    "DbType",
    "DocumentIntelligenceSettings",
    "Environment",
    "FoundrySettings",
    "IdentitySettings",
    "IndexStore",
    "IngestionTrigger",
    "NetworkSettings",
    "ObservabilitySettings",
    "OpenAISettings",
    "OrchestratorSettings",
    "SearchSettings",
    "SpeechSettings",
    "StorageSettings",
    "get_settings",
]
