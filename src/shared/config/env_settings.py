"""Pydantic BaseSettings for all environment variables.

Replaces the legacy EnvHelper singleton with a validated, typed configuration
object. All Azure service settings are grouped into nested models.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")

    model: str = "gpt-4o"
    endpoint: str = ""
    api_key: str = ""
    api_version: str = "2024-10-21"
    temperature: float = 0.0
    max_tokens: int = 1000
    top_p: float = 1.0
    stop_sequence: str = ""
    system_message: str = "You are an AI assistant that helps people find information."
    embedding_model: str = "text-embedding-ada-002"
    vision_model: str = ""
    stream: bool = True


class AzureSearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")

    service: str = ""
    index: str = ""
    key: str = ""
    conversations_log_index: str = ""
    use_semantic_search: bool = False
    semantic_search_config: str = "my-semantic-config"
    top_k: int = 5
    enable_in_domain: bool = True
    content_column: str = "content"
    content_vector_column: str = "content_vector"
    filename_column: str = "filename"
    title_column: str = "title"
    url_column: str = "url"
    fields_metadata: str = ""
    chunk_column: str = "chunk"
    offset_column: str = "offset"
    page_number_column: str = "page_number"
    use_integrated_vectorization: bool = False
    dimensions: int | None = None
    filter: str | None = None


class AzureStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_BLOB_")

    account_name: str = ""
    account_key: str = ""
    container_name: str = ""


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    database_type: str = Field(default="CosmosDB", alias="DATABASE_TYPE")
    azure_cosmosdb_account: str = Field(default="", alias="AZURE_COSMOSDB_ACCOUNT")
    azure_cosmosdb_database: str = Field(default="", alias="AZURE_COSMOSDB_DATABASE")
    azure_cosmosdb_conversations_container: str = Field(
        default="", alias="AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"
    )
    azure_cosmosdb_account_key: str = Field(default="", alias="AZURE_COSMOSDB_ACCOUNT_KEY")
    azure_cosmosdb_enable_feedback: bool = Field(
        default=False, alias="AZURE_COSMOSDB_ENABLE_FEEDBACK"
    )
    postgresql_connection_string: str = Field(default="", alias="POSTGRESQL_CONNECTION_STRING")


class SpeechSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SPEECH_")

    key: str = ""
    service_region: str = ""


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    azure_auth_type: str = Field(default="keys", alias="AZURE_AUTH_TYPE")
    azure_token_provider_scope: str = Field(
        default="https://cognitiveservices.azure.com/.default",
        alias="AZURE_TOKEN_PROVIDER_SCOPE",
    )
    managed_identity_resource_id: str = Field(
        default="", alias="AZURE_MANAGED_IDENTITY_RESOURCE_ID"
    )


class EnvSettings(BaseSettings):
    """Root settings object aggregating all service-specific settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nested settings
    openai: AzureOpenAISettings = AzureOpenAISettings()
    search: AzureSearchSettings = AzureSearchSettings()
    storage: AzureStorageSettings = AzureStorageSettings()
    database: DatabaseSettings = DatabaseSettings()
    speech: SpeechSettings = SpeechSettings()
    auth: AuthSettings = AuthSettings()

    # App-level settings
    conversation_flow: str = Field(default="custom", alias="CONVERSATION_FLOW")
    log_level: str = Field(default="INFO", alias="LOGLEVEL")
    applicationinsights_enabled: bool = Field(
        default=False, alias="APPLICATIONINSIGHTS_ENABLED"
    )
    orchestration_strategy: str = Field(
        default="openai_function", alias="ORCHESTRATION_STRATEGY"
    )
    azure_content_safety_endpoint: str = Field(
        default="", alias="AZURE_CONTENT_SAFETY_ENDPOINT"
    )
    azure_content_safety_key: str = Field(
        default="", alias="AZURE_CONTENT_SAFETY_KEY"
    )
    enable_content_safety: bool = Field(
        default=False, alias="AZURE_CONTENT_SAFETY_ENABLED"
    )
    azure_speech_region_endpoint: str = Field(
        default="", alias="AZURE_SPEECH_REGION_ENDPOINT"
    )
    azure_function_url: str = Field(default="", alias="AZURE_FUNCTION_URL")
    azure_function_key: str = Field(default="", alias="AZURE_FUNCTION_KEY")
    open_ai_functions_system_prompt: str = Field(
        default="", alias="OPEN_AI_FUNCTIONS_SYSTEM_PROMPT"
    )
    load_config_from_blob_storage: bool = Field(
        default=False, alias="LOAD_CONFIG_FROM_BLOB_STORAGE"
    )
