# database_factory.py
from ..helpers.env_helper import EnvHelper
from .cosmosdb import CosmosConversationClient
from .postgresdbservice import PostgresConversationClient
from azure.identity import DefaultAzureCredential
from ..helpers.config.database_type import DatabaseType

class DatabaseFactory:
    @staticmethod
    def get_conversation_client():
        env_helper: EnvHelper = EnvHelper()
        if env_helper.DATABASE_TYPE ==  DatabaseType.COSMOS_DB.value:
            cosmos_endpoint = (
                f"https://{env_helper.AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/"
            )
            credential = (
                DefaultAzureCredential()
                if not env_helper.AZURE_COSMOSDB_ACCOUNT_KEY
                else env_helper.AZURE_COSMOSDB_ACCOUNT_KEY
            )
            return CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=env_helper.AZURE_COSMOSDB_DATABASE,
                container_name=env_helper.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER,
                enable_message_feedback=env_helper.AZURE_COSMOSDB_ENABLE_FEEDBACK,
            )
        elif env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value:
            return PostgresConversationClient(
                user=env_helper.POSTGRESQL_USER,
                host=env_helper.POSTGRESQL_HOST,
                database=env_helper.POSTGRESQL_DATABASE,
            )
        else:
            raise ValueError(
                "Unsupported DATABASE_TYPE. Please set DATABASE_TYPE to 'CosmosDB' or 'PostgreSQL'."
            )
