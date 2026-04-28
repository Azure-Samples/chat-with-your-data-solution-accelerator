"""Typed runtime configuration for the v2 stack.

Pillar: Stable Core
Phase: 2

`AppSettings` composes ~9 small `BaseSettings` models, one per Azure
subsystem, that read **only** the `AZURE_*` env vars emitted by
`v2/infra/main.bicep` outputs (verified list of 37 vars as of Phase
1.2). The orchestrator namespace uses the runtime-tunable `CWYD_`
prefix because it is not infra-pinned.

Design rules (binding):

* No Key Vault. No secrets in fields. Every credential is acquired at
  runtime via Managed Identity through the `providers/credentials/`
  registry domain (Phase 2 task #11).
* Conditional Bicep outputs (cosmos / postgres / search / monitoring /
  vnet) default to empty strings here, mirroring the Bicep convention
  that "off" emits `''`. A `model_validator` on `DatabaseSettings`
  enforces that the side matching `AZURE_DB_TYPE` is populated.
* `get_settings()` is a `@lru_cache(maxsize=1)` singleton, **not** a
  module-level instance, so tests can call `get_settings.cache_clear()`
  between env-var permutations and FastAPI can `Depends(get_settings)`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Per-subsystem settings
# ---------------------------------------------------------------------------


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
    reasoning_deployment: str = ""
    embedding_deployment: str = ""
    temperature: float = 0.0
    max_tokens: int = 1000


class DatabaseSettings(BaseSettings):
    """Selects the chat-history backend AND the vector index store.

    `db_type` is the registry key passed to
    `providers.chat_history.create(...)`; `index_store` is passed to
    `providers.search.create(...)` / `providers.embedders.create(...)`.
    """

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    db_type: Literal["cosmosdb", "postgresql"] = "cosmosdb"
    index_store: Literal["AzureSearch", "pgvector"] = "AzureSearch"

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
        # go through `chat_history.create(db_type, ...)` / `search.create(
        # index_store, ...)` per Hard Rule #4.
        if self.db_type == "cosmosdb":  # noqa: registry-dispatch -- config validator
            if not self.cosmos_endpoint:
                raise ValueError(
                    "AZURE_DB_TYPE=cosmosdb requires AZURE_COSMOS_ENDPOINT to be set."
                )
            if self.index_store != "AzureSearch":
                raise ValueError(
                    "AZURE_DB_TYPE=cosmosdb requires AZURE_INDEX_STORE=AzureSearch."
                )
        else:  # postgresql
            if not self.postgres_endpoint:
                raise ValueError(
                    "AZURE_DB_TYPE=postgresql requires AZURE_POSTGRES_ENDPOINT to be set."
                )
            if self.index_store != "pgvector":
                raise ValueError(
                    "AZURE_DB_TYPE=postgresql requires AZURE_INDEX_STORE=pgvector."
                )
        return self


class SearchSettings(BaseSettings):
    """Azure AI Search (cosmosdb mode only; empty otherwise)."""

    model_config = SettingsConfigDict(env_prefix="AZURE_AI_SEARCH_", extra="ignore")

    endpoint: str = ""
    name: str = ""
    index: str = "cwyd-index"
    use_semantic_search: bool = True
    top_k: int = 5


class StorageSettings(BaseSettings):
    """Shared storage account (RAG documents + indexing queues)."""

    model_config = SettingsConfigDict(env_prefix="AZURE_", extra="ignore")

    storage_account_name: str = ""
    storage_blob_endpoint: str = ""
    documents_container: str = ""
    doc_processing_queue: str = ""


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


class OrchestratorSettings(BaseSettings):
    """Runtime-tunable orchestrator selection (registry key).

    Distinct namespace (`CWYD_`) because the orchestrator is **not** an
    infra-pinned value -- the admin UI and tests need to flip it
    without redeploying Bicep.
    """

    model_config = SettingsConfigDict(env_prefix="CWYD_ORCHESTRATOR_", extra="ignore")

    name: Literal["langgraph", "agent_framework"] = "langgraph"


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


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

    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    foundry: FoundrySettings = Field(default_factory=FoundrySettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)


# ---------------------------------------------------------------------------
# Cached accessor (FastAPI Depends-friendly)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the process-wide `AppSettings` singleton.

    Tests should call `get_settings.cache_clear()` between env-var
    permutations.
    """
    return AppSettings()


__all__ = [
    "AppSettings",
    "DatabaseSettings",
    "FoundrySettings",
    "IdentitySettings",
    "NetworkSettings",
    "ObservabilitySettings",
    "OpenAISettings",
    "OrchestratorSettings",
    "SearchSettings",
    "StorageSettings",
    "get_settings",
]
