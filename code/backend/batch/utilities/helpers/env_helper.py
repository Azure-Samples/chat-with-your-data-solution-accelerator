import json
import os
import logging
import threading
from dotenv import load_dotenv
from azure.identity import get_bearer_token_provider
from .azure_credential_utils import get_azure_credential
from azure.keyvault.secrets import SecretClient

from ..orchestrator.orchestration_strategy import OrchestrationStrategy
from ..helpers.config.conversation_flow import ConversationFlow
from ..helpers.config.database_type import DatabaseType

logger = logging.getLogger(__name__)


class EnvHelper:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                instance = super(EnvHelper, cls).__new__(cls)
                instance.__load_config()
                cls._instance = instance
            return cls._instance

    def __load_config(self, **kwargs) -> None:
        load_dotenv()

        logger.info("Initializing EnvHelper")

        # Wrapper for Azure Key Vault
        self.secretHelper = SecretHelper()

        self.LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()

        # Azure
        self.AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        self.AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "")

        # Azure Search
        self.AZURE_SEARCH_SERVICE = os.getenv("AZURE_SEARCH_SERVICE", "")
        self.AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "")
        self.AZURE_SEARCH_USE_SEMANTIC_SEARCH = self.get_env_var_bool(
            "AZURE_SEARCH_USE_SEMANTIC_SEARCH", "False"
        )
        self.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = os.getenv(
            "AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", "default"
        )
        self.AZURE_SEARCH_INDEX_IS_PRECHUNKED = os.getenv(
            "AZURE_SEARCH_INDEX_IS_PRECHUNKED", ""
        )
        self.AZURE_SEARCH_FILTER = os.getenv("AZURE_SEARCH_FILTER", "")
        self.AZURE_SEARCH_TOP_K = self.get_env_var_int("AZURE_SEARCH_TOP_K", 5)
        self.AZURE_SEARCH_ENABLE_IN_DOMAIN = (
            os.getenv("AZURE_SEARCH_ENABLE_IN_DOMAIN", "true").lower() == "true"
        )
        self.AZURE_SEARCH_FIELDS_ID = os.getenv("AZURE_SEARCH_FIELDS_ID", "id")
        self.AZURE_SEARCH_CONTENT_COLUMN = os.getenv(
            "AZURE_SEARCH_CONTENT_COLUMN", "content"
        )
        self.AZURE_SEARCH_CONTENT_VECTOR_COLUMN = os.getenv(
            "AZURE_SEARCH_CONTENT_VECTOR_COLUMN", "content_vector"
        )
        self.AZURE_SEARCH_DIMENSIONS = os.getenv("AZURE_SEARCH_DIMENSIONS", "1536")
        self.AZURE_SEARCH_FILENAME_COLUMN = os.getenv(
            "AZURE_SEARCH_FILENAME_COLUMN", "filepath"
        )
        self.AZURE_SEARCH_TITLE_COLUMN = os.getenv("AZURE_SEARCH_TITLE_COLUMN", "title")
        self.AZURE_SEARCH_URL_COLUMN = os.getenv("AZURE_SEARCH_URL_COLUMN", "url")
        self.AZURE_SEARCH_FIELDS_TAG = os.getenv("AZURE_SEARCH_FIELDS_TAG", "tag")
        self.AZURE_SEARCH_FIELDS_METADATA = os.getenv(
            "AZURE_SEARCH_FIELDS_METADATA", "metadata"
        )
        self.AZURE_SEARCH_SOURCE_COLUMN = os.getenv(
            "AZURE_SEARCH_SOURCE_COLUMN", "source"
        )
        self.AZURE_SEARCH_TEXT_COLUMN = os.getenv("AZURE_SEARCH_TEXT_COLUMN", "text")
        self.AZURE_SEARCH_LAYOUT_TEXT_COLUMN = os.getenv(
            "AZURE_SEARCH_LAYOUT_TEXT_COLUMN", "layoutText"
        )
        self.AZURE_SEARCH_CHUNK_COLUMN = os.getenv("AZURE_SEARCH_CHUNK_COLUMN", "chunk")
        self.AZURE_SEARCH_OFFSET_COLUMN = os.getenv(
            "AZURE_SEARCH_OFFSET_COLUMN", "offset"
        )
        self.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX = os.getenv(
            "AZURE_SEARCH_CONVERSATIONS_LOG_INDEX", "conversations"
        )
        self.AZURE_SEARCH_DOC_UPLOAD_BATCH_SIZE = os.getenv(
            "AZURE_SEARCH_DOC_UPLOAD_BATCH_SIZE", 100
        )
        # Integrated Vectorization
        self.AZURE_SEARCH_DATASOURCE_NAME = os.getenv(
            "AZURE_SEARCH_DATASOURCE_NAME", ""
        )
        self.AZURE_SEARCH_INDEXER_NAME = os.getenv("AZURE_SEARCH_INDEXER_NAME", "")

        # Chat History DB Integration Settings
        # Set default values based on DATABASE_TYPE
        self.DATABASE_TYPE = (
            os.getenv("DATABASE_TYPE", "").strip() or DatabaseType.COSMOSDB.value
        )
        # Cosmos DB configuration
        if self.DATABASE_TYPE == DatabaseType.COSMOSDB.value:
            azure_cosmosdb_info = self.get_info_from_env("AZURE_COSMOSDB_INFO", "")
            if azure_cosmosdb_info:
                self.AZURE_COSMOSDB_DATABASE = azure_cosmosdb_info.get(
                    "databaseName", ""
                )
                self.AZURE_COSMOSDB_ACCOUNT = azure_cosmosdb_info.get("accountName", "")
                self.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER = azure_cosmosdb_info.get(
                    "containerName", ""
                )
            else:
                self.AZURE_COSMOSDB_DATABASE = os.getenv(
                    "AZURE_COSMOSDB_DATABASE_NAME", ""
                )
                self.AZURE_COSMOSDB_ACCOUNT = os.getenv(
                    "AZURE_COSMOSDB_ACCOUNT_NAME", ""
                )
                self.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER = os.getenv(
                    "AZURE_COSMOSDB_CONVERSATIONS_CONTAINER_NAME", ""
                )
            self.AZURE_COSMOSDB_ACCOUNT_KEY = self.secretHelper.get_secret(
                "AZURE_COSMOSDB_ACCOUNT_KEY"
            )
            self.AZURE_COSMOSDB_ENABLE_FEEDBACK = (
                os.getenv("AZURE_COSMOSDB_ENABLE_FEEDBACK", "false").lower() == "true"
            )
            self.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = self.get_env_var_bool(
                "AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION", "False"
            )
            self.USE_ADVANCED_IMAGE_PROCESSING = self.get_env_var_bool(
                "USE_ADVANCED_IMAGE_PROCESSING", "False"
            )
            self.CONVERSATION_FLOW = os.getenv("CONVERSATION_FLOW", "custom")
            # Orchestration Settings
            self.ORCHESTRATION_STRATEGY = os.getenv(
                "ORCHESTRATION_STRATEGY", "openai_function"
            )
        # PostgreSQL configuration
        elif self.DATABASE_TYPE == DatabaseType.POSTGRESQL.value:
            self.AZURE_POSTGRES_SEARCH_TOP_K = self.get_env_var_int(
                "AZURE_POSTGRES_SEARCH_TOP_K", 5
            )
            azure_postgresql_info = self.get_info_from_env("AZURE_POSTGRESQL_INFO", "")
            if azure_postgresql_info:
                self.POSTGRESQL_USER = azure_postgresql_info.get("user", "")
                self.POSTGRESQL_DATABASE = azure_postgresql_info.get("dbname", "")
                self.POSTGRESQL_HOST = azure_postgresql_info.get("host", "")
            else:
                self.POSTGRESQL_USER = os.getenv("AZURE_POSTGRESQL_USER", "")
                self.POSTGRESQL_DATABASE = os.getenv(
                    "AZURE_POSTGRESQL_DATABASE_NAME", ""
                )
                self.POSTGRESQL_HOST = os.getenv("AZURE_POSTGRESQL_HOST_NAME", "")
            # Ensure integrated vectorization is disabled for PostgreSQL
            self.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False
            self.USE_ADVANCED_IMAGE_PROCESSING = False
            self.CONVERSATION_FLOW = ConversationFlow.CUSTOM.value
            self.ORCHESTRATION_STRATEGY = OrchestrationStrategy.SEMANTIC_KERNEL.value
        else:
            raise ValueError(
                "Unsupported DATABASE_TYPE. Please set DATABASE_TYPE to 'CosmosDB' or 'PostgreSQL'."
            )

        self.AZURE_AUTH_TYPE = os.getenv("AZURE_AUTH_TYPE", "keys")
        # Azure OpenAI
        self.AZURE_OPENAI_RESOURCE = os.getenv("AZURE_OPENAI_RESOURCE", "")
        # Fetch AZURE_OPENAI_MODEL_INFO from environment
        azure_openai_model_info = self.get_info_from_env("AZURE_OPENAI_MODEL_INFO", "")

        if azure_openai_model_info:
            # If AZURE_OPENAI_MODEL_INFO exists
            self.AZURE_OPENAI_MODEL = azure_openai_model_info.get("model", "")
            self.AZURE_OPENAI_MODEL_NAME = azure_openai_model_info.get("modelName", "")
        else:
            # Otherwise, fallback to individual environment variables
            self.AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL", "gpt-4.1")
            self.AZURE_OPENAI_MODEL_NAME = os.getenv(
                "AZURE_OPENAI_MODEL_NAME", "gpt-4.1"
            )

        self.AZURE_OPENAI_VISION_MODEL = os.getenv("AZURE_OPENAI_VISION_MODEL", "gpt-4")
        self.AZURE_OPENAI_TEMPERATURE = os.getenv("AZURE_OPENAI_TEMPERATURE", "0")
        self.AZURE_OPENAI_TOP_P = os.getenv("AZURE_OPENAI_TOP_P", "1.0")
        self.AZURE_OPENAI_MAX_TOKENS = os.getenv("AZURE_OPENAI_MAX_TOKENS", "1000")
        self.AZURE_OPENAI_STOP_SEQUENCE = os.getenv("AZURE_OPENAI_STOP_SEQUENCE", "")
        self.AZURE_OPENAI_SYSTEM_MESSAGE = os.getenv(
            "AZURE_OPENAI_SYSTEM_MESSAGE",
            "You are an AI assistant that helps people find information.",
        )
        self.AZURE_OPENAI_API_VERSION = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-01"
        )
        self.AZURE_OPENAI_STREAM = os.getenv("AZURE_OPENAI_STREAM", "true")

        # Fetch AZURE_OPENAI_EMBEDDING_MODEL_INFO from environment
        azure_openai_embedding_model_info = self.get_info_from_env(
            "AZURE_OPENAI_EMBEDDING_MODEL_INFO", ""
        )
        if azure_openai_embedding_model_info:
            # If AZURE_OPENAI_EMBEDDING_MODEL_INFO exists
            self.AZURE_OPENAI_EMBEDDING_MODEL = azure_openai_embedding_model_info.get(
                "model", ""
            )
        else:
            # Otherwise, fallback to individual environment variable
            self.AZURE_OPENAI_EMBEDDING_MODEL = os.getenv(
                "AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"
            )

        self.SHOULD_STREAM = (
            True if self.AZURE_OPENAI_STREAM.lower() == "true" else False
        )

        self.AZURE_TOKEN_PROVIDER = get_bearer_token_provider(
            get_azure_credential(), "https://cognitiveservices.azure.com/.default"
        )
        self.ADVANCED_IMAGE_PROCESSING_MAX_IMAGES = self.get_env_var_int(
            "ADVANCED_IMAGE_PROCESSING_MAX_IMAGES", 1
        )
        self.AZURE_COMPUTER_VISION_ENDPOINT = os.getenv(
            "AZURE_COMPUTER_VISION_ENDPOINT"
        )
        self.AZURE_COMPUTER_VISION_TIMEOUT = self.get_env_var_float(
            "AZURE_COMPUTER_VISION_TIMEOUT", 30
        )
        self.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION = os.getenv(
            "AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION", "2024-02-01"
        )
        self.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION = os.getenv(
            "AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION", "2023-04-15"
        )

        # Initialize Azure keys based on authentication type and environment settings.
        # When AZURE_AUTH_TYPE is "rbac", azure keys are None or an empty string.
        if self.AZURE_AUTH_TYPE == "rbac":
            self.AZURE_SEARCH_KEY = None
            self.AZURE_OPENAI_API_KEY = ""
            self.AZURE_SPEECH_KEY = None
            self.AZURE_COMPUTER_VISION_KEY = None
        else:
            self.AZURE_SEARCH_KEY = self.secretHelper.get_secret("AZURE_SEARCH_KEY")
            self.AZURE_OPENAI_API_KEY = self.secretHelper.get_secret(
                "AZURE_OPENAI_API_KEY"
            )
            self.AZURE_SPEECH_KEY = self.secretHelper.get_secret(
                "AZURE_SPEECH_SERVICE_KEY"
            )
            self.AZURE_COMPUTER_VISION_KEY = self.secretHelper.get_secret(
                "AZURE_COMPUTER_VISION_KEY"
            )

        # Set env for Azure OpenAI
        self.AZURE_OPENAI_ENDPOINT = os.environ.get(
            "AZURE_OPENAI_ENDPOINT",
            f"https://{self.AZURE_OPENAI_RESOURCE}.openai.azure.com/",
        )

        # Set env for OpenAI SDK
        self.OPENAI_API_TYPE = "azure" if self.AZURE_AUTH_TYPE == "keys" else "azure_ad"
        self.OPENAI_API_KEY = self.AZURE_OPENAI_API_KEY
        self.OPENAI_API_VERSION = self.AZURE_OPENAI_API_VERSION
        os.environ["OPENAI_API_TYPE"] = self.OPENAI_API_TYPE
        os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY
        os.environ["OPENAI_API_VERSION"] = self.OPENAI_API_VERSION
        # Azure Functions - Batch processing
        self.BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:7071")
        self.FUNCTION_KEY = os.getenv("FUNCTION_KEY")
        self.AzureWebJobsStorage = os.getenv("AzureWebJobsStorage", "")
        self.DOCUMENT_PROCESSING_QUEUE_NAME = os.getenv(
            "DOCUMENT_PROCESSING_QUEUE_NAME", "doc-processing"
        )
        # Azure Blob Storage
        azure_blob_storage_info = self.get_info_from_env("AZURE_BLOB_STORAGE_INFO", "")
        if azure_blob_storage_info:
            # If AZURE_BLOB_STORAGE_INFO exists
            self.AZURE_BLOB_ACCOUNT_NAME = azure_blob_storage_info.get(
                "accountName", ""
            )
            self.AZURE_BLOB_ACCOUNT_KEY = self.secretHelper.get_secret_from_json(
                azure_blob_storage_info.get("accountKey", "")
            )
            self.AZURE_BLOB_CONTAINER_NAME = azure_blob_storage_info.get(
                "containerName", ""
            )
        else:
            # Otherwise, fallback to individual environment variables
            self.AZURE_BLOB_ACCOUNT_NAME = os.getenv("AZURE_BLOB_ACCOUNT_NAME", "")
            self.AZURE_BLOB_ACCOUNT_KEY = self.secretHelper.get_secret(
                "AZURE_BLOB_ACCOUNT_KEY"
            )
            self.AZURE_BLOB_CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER_NAME", "")
        self.AZURE_STORAGE_ACCOUNT_ENDPOINT = os.getenv(
            "AZURE_STORAGE_ACCOUNT_ENDPOINT",
            f"https://{self.AZURE_BLOB_ACCOUNT_NAME}.blob.core.windows.net/",
        )

        # Azure Form Recognizer
        azure_form_recognizer_info = self.get_info_from_env(
            "AZURE_FORM_RECOGNIZER_INFO", ""
        )
        if azure_form_recognizer_info:
            # If AZURE_FORM_RECOGNIZER_INFO exists
            self.AZURE_FORM_RECOGNIZER_ENDPOINT = azure_form_recognizer_info.get(
                "endpoint", ""
            )
            self.AZURE_FORM_RECOGNIZER_KEY = self.secretHelper.get_secret_from_json(
                azure_form_recognizer_info.get("key", "")
            )
        else:
            # Otherwise, fallback to individual environment variables
            self.AZURE_FORM_RECOGNIZER_ENDPOINT = os.getenv(
                "AZURE_FORM_RECOGNIZER_ENDPOINT", ""
            )
            self.AZURE_FORM_RECOGNIZER_KEY = self.secretHelper.get_secret(
                "AZURE_FORM_RECOGNIZER_KEY"
            )

        # Azure App Insights
        # APPLICATIONINSIGHTS_ENABLED will be True when the application runs in App Service
        self.APPLICATIONINSIGHTS_ENABLED = self.get_env_var_bool(
            "APPLICATIONINSIGHTS_ENABLED", "False"
        )

        # Azure AI Content Safety
        self.AZURE_CONTENT_SAFETY_ENDPOINT = os.getenv(
            "AZURE_CONTENT_SAFETY_ENDPOINT", ""
        )
        if (
            "https" not in self.AZURE_CONTENT_SAFETY_ENDPOINT
            and "api.cognitive.microsoft.com" not in self.AZURE_CONTENT_SAFETY_ENDPOINT
        ):
            self.AZURE_CONTENT_SAFETY_ENDPOINT = self.AZURE_FORM_RECOGNIZER_ENDPOINT
        self.AZURE_CONTENT_SAFETY_KEY = self.secretHelper.get_secret(
            "AZURE_CONTENT_SAFETY_KEY"
        )
        # Speech Service
        self.AZURE_SPEECH_SERVICE_NAME = os.getenv("AZURE_SPEECH_SERVICE_NAME", "")
        self.AZURE_SPEECH_SERVICE_REGION = os.getenv("AZURE_SPEECH_SERVICE_REGION")
        self.AZURE_SPEECH_RECOGNIZER_LANGUAGES = self.get_env_var_array(
            "AZURE_SPEECH_RECOGNIZER_LANGUAGES", "en-US"
        )
        self.AZURE_SPEECH_REGION_ENDPOINT = os.environ.get(
            "AZURE_SPEECH_REGION_ENDPOINT",
            f"https://{self.AZURE_SPEECH_SERVICE_REGION}.api.cognitive.microsoft.com/",
        )

        self.LOAD_CONFIG_FROM_BLOB_STORAGE = self.get_env_var_bool(
            "LOAD_CONFIG_FROM_BLOB_STORAGE"
        )

        self.AZURE_ML_WORKSPACE_NAME = os.getenv("AZURE_ML_WORKSPACE_NAME", "")

        self.PROMPT_FLOW_ENDPOINT_NAME = os.getenv("PROMPT_FLOW_ENDPOINT_NAME", "")

        self.PROMPT_FLOW_DEPLOYMENT_NAME = os.getenv("PROMPT_FLOW_DEPLOYMENT_NAME", "")

        self.OPEN_AI_FUNCTIONS_SYSTEM_PROMPT = os.getenv(
            "OPEN_AI_FUNCTIONS_SYSTEM_PROMPT", ""
        )
        self.SEMANTIC_KERNEL_SYSTEM_PROMPT = os.getenv(
            "SEMANTIC_KERNEL_SYSTEM_PROMPT", ""
        )

        self.ENFORCE_AUTH = self.get_env_var_bool("ENFORCE_AUTH", "True")

        logger.info("Initializing EnvHelper completed")

    def is_chat_model(self):
        if "gpt-4" in self.AZURE_OPENAI_MODEL_NAME.lower():
            return True
        return False

    def get_env_var_bool(self, var_name: str, default: str = "True") -> bool:
        return os.getenv(var_name, default).lower() == "true"

    def get_env_var_array(self, var_name: str, default: str = ""):
        return os.getenv(var_name, default).split(",")

    def get_env_var_int(self, var_name: str, default: int):
        return int(os.getenv(var_name, default))

    def get_env_var_float(self, var_name: str, default: float):
        return float(os.getenv(var_name, default))

    def is_auth_type_keys(self):
        return self.AZURE_AUTH_TYPE == "keys"

    def get_info_from_env(self, env_var: str, default_info: str) -> dict:
        # Fetch and parse model info from the environment variable.
        info_str = os.getenv(env_var, default_info)
        # Handle escaped characters in the JSON string by wrapping it in double quotes for parsing.
        if "\\" in info_str:
            info_str = json.loads(f'"{info_str}"')
        return {} if not info_str else json.loads(info_str)

    @staticmethod
    def check_env():
        for attr, value in EnvHelper().__dict__.items():
            if value == "":
                logger.warning(f"{attr} is not set in the environment variables.")

    @classmethod
    def clear_instance(cls):
        if cls._instance is not None:
            cls._instance = None


class SecretHelper:
    def __init__(self) -> None:
        """
        Initializes an instance of the SecretHelper class.

        The constructor sets the USE_KEY_VAULT attribute based on the value of the USE_KEY_VAULT environment variable.
        If USE_KEY_VAULT is set to "true" (case-insensitive), it initializes a SecretClient object using the
        AZURE_KEY_VAULT_ENDPOINT environment variable and the get_azure_credential.

        Args:
            None

        Returns:
            None
        """
        self.USE_KEY_VAULT = os.getenv("USE_KEY_VAULT", "").lower() == "true"
        self.secret_client = None
        if self.USE_KEY_VAULT:
            self.secret_client = SecretClient(
                os.environ.get("AZURE_KEY_VAULT_ENDPOINT"), get_azure_credential()
            )

    def get_secret(self, secret_name: str) -> str:
        """
        Retrieves the value of a secret from the environment variables or Azure Key Vault.

        Args:
            secret_name (str): The name of the secret or "".

        Returns:
            str: The value of the secret.

        Raises:
            None

        """
        secret_name_value = os.getenv(secret_name, "")
        return (
            self.secret_client.get_secret(secret_name_value).value
            if self.USE_KEY_VAULT and secret_name_value
            else os.getenv(secret_name, "")
        )

    def get_secret_from_json(self, secret_name: str) -> str:
        return (
            self.secret_client.get_secret(secret_name).value
            if self.USE_KEY_VAULT and secret_name
            else secret_name
        )
