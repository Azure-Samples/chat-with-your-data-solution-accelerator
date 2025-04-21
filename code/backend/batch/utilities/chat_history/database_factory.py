# database_factory.py
import os
from ..helpers.env_helper import EnvHelper
from .postgresdbservice import PostgresConversationClient

# from azure.identity import DefaultAzureCredential # disable for local dev to ensure pre-commit hooks pass
from ..helpers.config.database_type import DatabaseType
import logging

logger = logging.getLogger(__name__)


class DatabaseFactory:
    @staticmethod
    def get_conversation_client():
        env_helper: EnvHelper = EnvHelper()

        if env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value:
            # Try to get environment variables from os.environ if not available through EnvHelper
            postgresql_user = getattr(
                env_helper, "POSTGRESQL_USER", None
            ) or os.environ.get("POSTGRESQL_USER", "postgres")
            postgresql_host = getattr(
                env_helper, "POSTGRESQL_HOST", None
            ) or os.environ.get("POSTGRESQL_HOST", "postgres")
            postgresql_database = getattr(
                env_helper, "POSTGRESQL_DATABASE", None
            ) or os.environ.get("POSTGRESQL_DB", "postgres")

            # Log the connection details for debugging
            logger.info(
                "Using PostgreSQL connection with user: %s, host: %s, database: %s",
                postgresql_user,
                postgresql_host,
                postgresql_database,
            )

            # Get password but don't pass it to PostgresConversationClient as it doesn't accept it
            # The client will use DefaultAzureCredential instead
            _ = getattr(env_helper, "POSTGRESQL_PASSWORD", None) or os.environ.get(
                "POSTGRESQL_PASSWORD", "postgres"
            )

            # Only pass the parameters that PostgresConversationClient accepts
            return PostgresConversationClient(
                user=postgresql_user,
                host=postgresql_host,
                database=postgresql_database,
            )
        else:
            raise ValueError(
                "Unsupported DATABASE_TYPE. Please set DATABASE_TYPE to 'CosmosDB' or 'PostgreSQL'."
            )

    @staticmethod
    def _validate_env_vars(required_vars, env_helper):
        # For local development, we'll skip strict validation
        if os.environ.get("ENVIRONMENT", "").lower() == "production":
            for var in required_vars:
                if not getattr(env_helper, var, None) and not os.environ.get(var):
                    raise ValueError(f"Environment variable {var} is required.")
