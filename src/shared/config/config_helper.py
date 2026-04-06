"""ConfigHelper: manages active.json configuration from blob storage."""

from __future__ import annotations

import json
import logging

from azure.storage.blob import BlobServiceClient

from .models import ConfigModel

logger = logging.getLogger(__name__)


class ConfigHelper:
    _config: ConfigModel | None = None

    @classmethod
    def get_active_config(
        cls,
        blob_client: BlobServiceClient,
        container: str = "config",
        blob_name: str = "active.json",
    ) -> ConfigModel:
        if cls._config is not None:
            return cls._config
        try:
            blob = blob_client.get_blob_client(container=container, blob=blob_name)
            data = json.loads(blob.download_blob().readall())
            cls._config = ConfigModel.model_validate(data)
        except Exception:
            logger.warning("Could not load active.json, using defaults")
            cls._config = ConfigModel()
        return cls._config

    @classmethod
    def save_config(
        cls,
        config: ConfigModel,
        blob_client: BlobServiceClient,
        container: str = "config",
        blob_name: str = "active.json",
    ) -> None:
        blob = blob_client.get_blob_client(container=container, blob=blob_name)
        blob.upload_blob(
            config.model_dump_json(indent=2),
            overwrite=True,
        )
        cls._config = config
        logger.info("Saved active.json to blob storage")

    @classmethod
    def clear_cache(cls) -> None:
        cls._config = None
