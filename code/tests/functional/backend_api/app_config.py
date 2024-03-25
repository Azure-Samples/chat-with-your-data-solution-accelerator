import logging
import os
from typing import Any, Dict


class AppConfig:
    config: Dict[str, Any] = {
        "AZURE_SPEECH_SERVICE_KEY": "some-azure-speech-service-key",
        "AZURE_SPEECH_SERVICE_REGION": "some-azure-speech-service-region",
        "APPINSIGHTS_ENABLED": "False",
        "AZURE_OPENAI_API_KEY": "some-azure-openai-api-key",
        "AZURE_SEARCH_KEY": "some-azure-search-key",
        "AZURE_CONTENT_SAFETY_KEY": "some-content_safety-key",
        "AZURE_OPENAI_EMBEDDING_MODEL": "some-embedding-model",
        "AZURE_OPENAI_MODEL": "some-openai-model",
        "AZURE_SEARCH_CONVERSATIONS_LOG_INDEX": "some-log-index",
        "LOAD_CONFIG_FROM_BLOB_STORAGE": "False",
        "TIKTOKEN_CACHE_DIR": f"{os.path.dirname(os.path.realpath(__file__))}/resources",
    }

    def __init__(self, config_overrides: Dict[str, Any] = {}) -> None:
        self.config = self.config | config_overrides

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value

    def get(self, key: str) -> Any:
        return self.config[key]

    def get_all(self) -> Dict[str, Any]:
        return self.config

    def apply_to_environment(self) -> None:
        for key, value in self.config.items():
            if value is not None:
                logging.info(f"Applying env var: {key}={value}")
                os.environ[key] = value
            else:
                logging.info(f"Removing env var: {key}")
                os.environ.pop(key, None)

    def remove_from_environment(self) -> None:
        for key in self.config.keys():
            logging.info(f"Removing env var: {key}")
            os.environ.pop(key, None)
