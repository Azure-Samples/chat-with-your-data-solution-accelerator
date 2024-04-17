import logging
import os

logger = logging.getLogger(__name__)


class AppConfig:
    config: dict[str, str | None] = {
        "AZURE_SPEECH_SERVICE_KEY": "some-azure-speech-service-key",
        "AZURE_SPEECH_SERVICE_REGION": "some-azure-speech-service-region",
        "SPEECH_RECOGNIZER_LANGUAGES": "en-US,es-ES",
        "APPINSIGHTS_ENABLED": "False",
        "AZURE_OPENAI_API_KEY": "some-azure-openai-api-key",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
        "AZURE_SEARCH_INDEX": "some-azure-search-index",
        "AZURE_SEARCH_KEY": "some-azure-search-key",
        "AZURE_SEARCH_FILTER": "some-search-filter",
        "AZURE_CONTENT_SAFETY_KEY": "some-content_safety-key",
        "AZURE_OPENAI_EMBEDDING_MODEL": "some-embedding-model",
        "AZURE_OPENAI_MODEL": "some-openai-model",
        "AZURE_SEARCH_CONVERSATIONS_LOG_INDEX": "some-log-index",
        "AZURE_OPENAI_STREAM": "True",
        "LOAD_CONFIG_FROM_BLOB_STORAGE": "False",
        "TIKTOKEN_CACHE_DIR": f"{os.path.dirname(os.path.realpath(__file__))}/resources",
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
            if value is not None:
                logger.info(f"Applying env var: {key}={value}")
                os.environ[key] = value
            else:
                logger.info(f"Removing env var: {key}")
                os.environ.pop(key, None)

    def remove_from_environment(self) -> None:
        for key in self.config.keys():
            logger.info(f"Removing env var: {key}")
            os.environ.pop(key, None)
