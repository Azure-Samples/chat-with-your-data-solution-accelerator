import os
import json
import logging
from string import Template
from .AzureBlobStorageHelper import AzureBlobStorageClient
from ..document_chunking.Strategies import ChunkingSettings, ChunkingStrategy
from ..document_loading import LoadingSettings, LoadingStrategy
from .DocumentProcessorHelper import Processor
from .OrchestratorHelper import (
    OrchestrationSettings,
    OrchestrationStrategy,
)
from .EnvHelper import EnvHelper

CONFIG_CONTAINER_NAME = "config"
CONFIG_FILE_NAME = "active.json"
logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config: dict):
        self.prompts = Prompts(config["prompts"])
        self.messages = Messages(config["messages"])
        self.example = Example(config["example"])
        self.logging = Logging(config["logging"])
        self.document_processors = [
            Processor(
                document_type=c["document_type"],
                chunking=(
                    ChunkingSettings(c["chunking"])
                    if c.get("use_advanced_image_processing", False) is False
                    else None
                ),
                loading=(
                    LoadingSettings(c["loading"])
                    if c.get("use_advanced_image_processing", False) is False
                    else None
                ),
                use_advanced_image_processing=c.get(
                    "use_advanced_image_processing", False
                ),
            )
            for c in config["document_processors"]
        ]
        self.env_helper = EnvHelper()
        self.default_orchestration_settings = {
            "strategy": self.env_helper.ORCHESTRATION_STRATEGY
        }
        self.orchestrator = OrchestrationSettings(
            config.get("orchestrator", self.default_orchestration_settings)
        )

    def get_available_document_types(self):
        document_types = [
            "txt",
            "pdf",
            "url",
            "html",
            "md",
            "jpeg",
            "jpg",
            "png",
            "docx",
        ]
        if self.env_helper.USE_ADVANCED_IMAGE_PROCESSING:
            document_types.extend(["tiff", "bmp"])

        return sorted(document_types)

    def get_available_chunking_strategies(self):
        return [c.value for c in ChunkingStrategy]

    def get_available_loading_strategies(self):
        return [c.value for c in LoadingStrategy]

    def get_available_orchestration_strategies(self):
        return [c.value for c in OrchestrationStrategy]


# TODO: Change to AnsweringChain or something, Prompts is not a good name
class Prompts:
    def __init__(self, prompts: dict):
        self.condense_question_prompt = prompts["condense_question_prompt"]
        self.answering_system_prompt = prompts["answering_system_prompt"]
        self.answering_user_prompt = prompts["answering_user_prompt"]
        self.post_answering_prompt = prompts["post_answering_prompt"]
        self.use_on_your_data_format = prompts["use_on_your_data_format"]
        self.enable_post_answering_prompt = prompts["enable_post_answering_prompt"]
        self.enable_content_safety = prompts["enable_content_safety"]


class Example:
    def __init__(self, example: dict):
        self.documents = example["documents"]
        self.user_question = example["user_question"]
        self.answer = example["answer"]


class Messages:
    def __init__(self, messages: dict):
        self.post_answering_filter = messages["post_answering_filter"]


class Logging:
    def __init__(self, logging: dict):
        self.log_user_interactions = logging["log_user_interactions"]
        self.log_tokens = logging["log_tokens"]


class ConfigHelper:
    _default_config = None

    @staticmethod
    def _set_new_config_properties(config: dict, default_config: dict):
        """
        Function used to set newer properties that will not be present in older configs.
        The function mutates the config object.
        """
        if config["prompts"].get("answering_system_prompt") is None:
            config["prompts"]["answering_system_prompt"] = default_config["prompts"][
                "answering_system_prompt"
            ]

        prompt_modified = (
            config["prompts"].get("answering_prompt")
            != default_config["prompts"]["answering_prompt"]
        )

        if config["prompts"].get("answering_user_prompt") is None:
            if prompt_modified:
                config["prompts"]["answering_user_prompt"] = config["prompts"].get(
                    "answering_prompt"
                )
            else:
                config["prompts"]["answering_user_prompt"] = default_config["prompts"][
                    "answering_user_prompt"
                ]

        if config["prompts"].get("use_on_your_data_format") is None:
            config["prompts"]["use_on_your_data_format"] = not prompt_modified

        if config.get("example") is None:
            config["example"] = default_config["example"]

    @staticmethod
    def get_active_config_or_default():
        env_helper = EnvHelper()
        config = ConfigHelper.get_default_config()

        if env_helper.LOAD_CONFIG_FROM_BLOB_STORAGE:
            blob_client = AzureBlobStorageClient(container_name=CONFIG_CONTAINER_NAME)

            if blob_client.file_exists(CONFIG_FILE_NAME):
                default_config = config
                config_file = blob_client.download_file(CONFIG_FILE_NAME)
                config = json.loads(config_file)

                ConfigHelper._set_new_config_properties(config, default_config)
            else:
                logger.info("Returning default config")

        return Config(config)

    @staticmethod
    def save_config_as_active(config):
        blob_client = AzureBlobStorageClient(container_name=CONFIG_CONTAINER_NAME)
        blob_client = blob_client.upload_file(
            json.dumps(config, indent=2),
            CONFIG_FILE_NAME,
            content_type="application/json",
        )

    @staticmethod
    def get_default_config():
        if ConfigHelper._default_config is None:
            env_helper = EnvHelper()

            config_file_path = os.path.join(
                os.path.dirname(__file__), "config", "default.json"
            )

            with open(config_file_path) as f:
                logging.info(f"Loading default config from {config_file_path}")
                ConfigHelper._default_config = json.loads(
                    Template(f.read()).substitute(
                        ORCHESTRATION_STRATEGY=env_helper.ORCHESTRATION_STRATEGY
                    )
                )
                if env_helper.USE_ADVANCED_IMAGE_PROCESSING:
                    ConfigHelper._append_advanced_image_processors()

        return ConfigHelper._default_config

    @staticmethod
    def _append_advanced_image_processors():
        image_file_types = ["jpeg", "jpg", "png", "tiff", "bmp"]
        ConfigHelper._remove_processors_for_file_types(image_file_types)
        ConfigHelper._default_config["document_processors"].extend(
            [
                {"document_type": file_type, "use_advanced_image_processing": True}
                for file_type in image_file_types
            ]
        )

    @staticmethod
    def _remove_processors_for_file_types(file_types: list[str]):
        document_processors = ConfigHelper._default_config["document_processors"]
        document_processors = [
            document_processor
            for document_processor in document_processors
            if document_processor["document_type"] not in file_types
        ]
        ConfigHelper._default_config["document_processors"] = document_processors

    @staticmethod
    def delete_config():
        blob_client = AzureBlobStorageClient(container_name=CONFIG_CONTAINER_NAME)
        blob_client.delete_file(CONFIG_FILE_NAME)
