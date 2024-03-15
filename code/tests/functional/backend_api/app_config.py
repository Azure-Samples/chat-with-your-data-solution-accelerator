import os
from typing import Any, Dict


class AppConfig:
    config: Dict[str, Any] = {
        "AZURE_SPEECH_SERVICE_KEY": "some-azure-speech-service-key",
        "AZURE_SPEECH_SERVICE_REGION": "some-azure-speech-service-region",
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
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def remove_from_environment(self) -> None:
        for key in self.config.keys():
            os.environ.pop(key, None)
