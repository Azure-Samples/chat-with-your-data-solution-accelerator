"""ConfigHelper: manages active.json configuration from blob storage."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

from .models import ConfigModel

logger = logging.getLogger(__name__)

_CONFIG_CONTAINER = "config"
_CONFIG_BLOB = "active.json"
_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "default.json")


def _load_default_config_dict() -> dict:
    """Load the default.json shipped with the package."""
    with open(_DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _set_new_config_properties(config: dict, default_config: dict) -> None:
    """Back-fill newer properties that may be absent in older saved configs."""
    prompts = config.setdefault("prompts", {})
    dp = default_config.get("prompts", {})

    if prompts.get("answering_system_prompt") is None:
        prompts["answering_system_prompt"] = dp.get("answering_system_prompt", "")

    prompt_modified = prompts.get("answering_prompt") != dp.get("answering_prompt")

    if prompts.get("answering_user_prompt") is None:
        prompts["answering_user_prompt"] = (
            prompts.get("answering_prompt") if prompt_modified else dp.get("answering_user_prompt", "")
        )

    if prompts.get("use_on_your_data_format") is None:
        prompts["use_on_your_data_format"] = not prompt_modified

    if config.get("example") is None:
        config["example"] = default_config.get("example", {})

    if prompts.get("ai_assistant_type") is None:
        prompts["ai_assistant_type"] = dp.get("ai_assistant_type", "default")

    if config.get("integrated_vectorization_config") is None:
        config["integrated_vectorization_config"] = default_config.get(
            "integrated_vectorization_config"
        )

    if prompts.get("conversational_flow") is None:
        prompts["conversational_flow"] = dp.get("conversational_flow", "custom")

    if config.get("enable_chat_history") is None:
        config["enable_chat_history"] = default_config.get("enable_chat_history", False)


class ConfigHelper:
    _config: ConfigModel | None = None

    @classmethod
    def get_active_config(
        cls,
        blob_client,
        container: str = _CONFIG_CONTAINER,
        blob_name: str = _CONFIG_BLOB,
    ) -> ConfigModel:
        if cls._config is not None:
            return cls._config
        try:
            blob = blob_client.get_blob_client(container=container, blob=blob_name)
            data = json.loads(blob.download_blob().readall())
            default_data = _load_default_config_dict()
            _set_new_config_properties(data, default_data)
            cls._config = ConfigModel.model_validate(data)
        except Exception:
            logger.warning("Could not load active.json from blob, using defaults")
            cls._config = ConfigModel.model_validate(_load_default_config_dict())
        return cls._config

    @classmethod
    @lru_cache
    def get_active_config_or_default(cls) -> ConfigModel:
        """Return cached config or load from default.json.

        If ``LOAD_CONFIG_FROM_BLOB_STORAGE`` is true, attempts blob storage
        first, falling back to the bundled default.json.
        """
        if cls._config is not None:
            return cls._config

        load_from_blob = (
            os.environ.get("LOAD_CONFIG_FROM_BLOB_STORAGE", "false").lower() == "true"
        )

        if load_from_blob:
            try:
                from azure.storage.blob import BlobServiceClient

                account_name = os.environ.get("AZURE_BLOB_ACCOUNT_NAME", "")
                account_key = os.environ.get("AZURE_BLOB_ACCOUNT_KEY", "")
                endpoint = f"https://{account_name}.blob.core.windows.net"

                if account_key:
                    client = BlobServiceClient(endpoint, credential=account_key)
                else:
                    from azure.identity import DefaultAzureCredential

                    client = BlobServiceClient(endpoint, credential=DefaultAzureCredential())

                return cls.get_active_config(client)
            except Exception:
                logger.warning("Blob config load failed, falling back to default.json")

        cls._config = ConfigModel.model_validate(_load_default_config_dict())
        return cls._config

    @classmethod
    def save_config(
        cls,
        config: ConfigModel,
        blob_client,
        container: str = _CONFIG_CONTAINER,
        blob_name: str = _CONFIG_BLOB,
    ) -> None:
        blob = blob_client.get_blob_client(container=container, blob=blob_name)
        blob.upload_blob(
            config.model_dump_json(indent=2),
            overwrite=True,
        )
        cls._config = config
        cls.get_active_config_or_default.cache_clear()
        logger.info("Saved active.json to blob storage")

    @classmethod
    def clear_cache(cls) -> None:
        cls._config = None
        cls.get_active_config_or_default.cache_clear()
