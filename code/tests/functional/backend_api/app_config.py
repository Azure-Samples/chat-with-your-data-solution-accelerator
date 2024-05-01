import logging
import os

logger = logging.getLogger(__name__)


class AppConfig:
    before_config: dict[str, str] = {}
    config: dict[str, str | None] = {
        "APPINSIGHTS_CONNECTION_STRING": "",
        "APPINSIGHTS_ENABLED": "False",
        "AZURE_AUTH_TYPE": "keys",
        "AZURE_BLOB_ACCOUNT_KEY": "some-blob-account-key",
        "AZURE_BLOB_ACCOUNT_NAME": "some-blob-account-name",
        "AZURE_BLOB_CONTAINER_NAME": "some-blob-container-name",
        "AZURE_CONTENT_SAFETY_ENDPOINT": "some-content-safety-endpoint",
        "AZURE_CONTENT_SAFETY_KEY": "some-content-safety-key",
        "AZURE_FORM_RECOGNIZER_ENDPOINT": "some-form-recognizer-endpoint",
        "AZURE_FORM_RECOGNIZER_KEY": "some-form-recognizer-key",
        "AZURE_KEY_VAULT_ENDPOINT": "some-key-vault-endpoint",
        "AZURE_OPENAI_API_KEY": "some-azure-openai-api-key",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
        "AZURE_OPENAI_EMBEDDING_MODEL": "some-embedding-model",
        "AZURE_OPENAI_ENDPOINT": "some-openai-endpoint",
        "AZURE_OPENAI_MAX_TOKENS": "1000",
        "AZURE_OPENAI_MODEL": "some-openai-model",
        "AZURE_OPENAI_MODEL_NAME": "some-openai-model-name",
        "AZURE_OPENAI_RESOURCE": "some-openai-resource",
        "AZURE_OPENAI_STREAM": "True",
        "AZURE_OPENAI_STOP_SEQUENCE": "",
        "AZURE_OPENAI_SYSTEM_MESSAGE": "You are an AI assistant that helps people find information.",
        "AZURE_OPENAI_TEMPERATURE": "0",
        "AZURE_OPENAI_TOP_P": "1.0",
        "AZURE_RESOURCE_GROUP": "some-resource-group",
        "AZURE_SEARCH_CONVERSATIONS_LOG_INDEX": "some-log-index",
        "AZURE_SEARCH_CONTENT_COLUMNS": "content",
        "AZURE_SEARCH_CONTENT_VECTOR_COLUMNS": "some-search-content-vector-columns",
        "AZURE_SEARCH_DIMENSIONS": "some-search-dimensions",
        "AZURE_SEARCH_ENABLE_IN_DOMAIN": "True",
        "AZURE_SEARCH_FIELDS_ID": "some-search-fields-id",
        "AZURE_SEARCH_FIELDS_METADATA": "some-search-fields-metadata",
        "AZURE_SEARCH_FIELDS_TAG": "some-search-fields-tag",
        "AZURE_SEARCH_FILENAME_COLUMN": "filepath",
        "AZURE_SEARCH_FILTER": "some-search-filter",
        "AZURE_SEARCH_INDEX": "some-azure-search-index",
        "AZURE_SEARCH_INDEX_IS_PRECHUNKED": "some-azure-search-index-is-prechunked",
        "AZURE_SEARCH_KEY": "some-azure-search-key",
        "AZURE_SEARCH_SERVICE": "some-azure-search-service",
        "AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG": "some-search-semantic-search-config",
        "AZURE_SEARCH_TITLE_COLUMN": "title",
        "AZURE_SEARCH_TOP_K": "5",
        "AZURE_SEARCH_URL_COLUMN": "url",
        "AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION": "False",
        "AZURE_SEARCH_INDEXER_NAME": "some-azure-search-indexer-name",
        "AZURE_SEARCH_DATASOURCE_NAME": "some-azure-search-datasource-name",
        "AZURE_SEARCH_IV_MAX_PAGE_LENGTH": "2000",
        "AZURE_SEARCH_IV_PAGE_OVERLAP_LENGTH": "500",
        "AZURE_SEARCH_USE_SEMANTIC_SEARCH": "False",
        "AZURE_SPEECH_REGION_ENDPOINT": "some-speech-region-endpoint",
        "AZURE_SPEECH_SERVICE_KEY": "some-azure-speech-service-key",
        "AZURE_SPEECH_SERVICE_NAME": "some-speech-service-name",
        "AZURE_SPEECH_SERVICE_REGION": "some-azure-speech-service-region",
        "AZURE_SUBSCRIPTION_ID": "some-subscription-id",
        "BACKEND_URL": "some-backend-url",
        "DOCUMENT_PROCESSING_QUEUE_NAME": "some-document-processing-queue-name",
        "FUNCTION_KEY": "some-function-key",
        "LOAD_CONFIG_FROM_BLOB_STORAGE": "False",
        "LOGLEVEL": "DEBUG",
        "ORCHESTRATION_STRATEGY": "openai_function",
        "AZURE_SPEECH_RECOGNIZER_LANGUAGES": "en-US,es-ES",
        "TIKTOKEN_CACHE_DIR": f"{os.path.dirname(os.path.realpath(__file__))}/resources",
        "USE_ADVANCED_IMAGE_PROCESSING": "False",
        "USE_KEY_VAULT": "False",
        # These values are set directly within EnvHelper, adding them here ensures
        # that they are removed from the environment when remove_from_environment() runs
        "OPENAI_API_TYPE": None,
        "OPENAI_API_KEY": None,
        "OPENAI_API_VERSION": None,
    }

    def __init__(self, config_overrides: dict[str, str | None] = {}) -> None:
        self.config = self.config | config_overrides

    def set(self, key: str, value: str | None) -> None:
        self.config[key] = value

    def get(self, key: str) -> str | None:
        return self.config[key]

    def get_all(self) -> dict[str, str | None]:
        return self.config

    def apply_to_environment(self) -> None:
        for key, value in self.config.items():
            current_config = os.environ.get(key)
            if current_config is not None:
                self.before_config[key] = current_config

            if value is not None:
                logger.info(f"Applying env var: {key}={value}")
                os.environ[key] = value
            else:
                logger.info(f"Removing env var: {key}")
                os.environ.pop(key, None)

    def remove_from_environment(self) -> None:
        for key in self.config.keys():
            if key in self.before_config:
                logger.info(f"Resetting env var: {key}")
                os.environ[key] = self.before_config[key]
            else:
                logger.info(f"Removing env var: {key}")
                os.environ.pop(key, None)
