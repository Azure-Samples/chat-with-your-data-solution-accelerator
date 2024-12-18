import pytest
from unittest.mock import patch, MagicMock
from backend.batch.utilities.helpers.config.database_type import DatabaseType
from backend.batch.utilities.chat_history.cosmosdb import CosmosConversationClient
from backend.batch.utilities.chat_history.database_factory import DatabaseFactory
from backend.batch.utilities.chat_history.postgresdbservice import (
    PostgresConversationClient,
)


@patch("backend.batch.utilities.chat_history.database_factory.DefaultAzureCredential")
@patch("backend.batch.utilities.chat_history.database_factory.EnvHelper")
@patch(
    "backend.batch.utilities.chat_history.database_factory.CosmosConversationClient",
    autospec=True,
)
def test_get_conversation_client_cosmos(
    mock_cosmos_client, mock_env_helper, mock_credential
):
    # Configure the EnvHelper mock
    mock_env_instance = mock_env_helper.return_value
    mock_env_instance.DATABASE_TYPE = DatabaseType.COSMOSDB.value
    mock_env_instance.AZURE_COSMOSDB_ACCOUNT = "cosmos_account"
    mock_env_instance.AZURE_COSMOSDB_DATABASE = "cosmos_database"
    mock_env_instance.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER = "conversations_container"
    mock_env_instance.AZURE_COSMOSDB_ENABLE_FEEDBACK = False
    mock_env_instance.AZURE_COSMOSDB_ACCOUNT_KEY = None

    mock_access_token = MagicMock()
    mock_access_token.token = "mock-access-token"
    mock_credential.return_value.get_token.return_value = mock_access_token
    mock_credential_instance = mock_credential.return_value

    # Mock the CosmosConversationClient instance
    mock_cosmos_instance = MagicMock(spec=CosmosConversationClient)
    mock_cosmos_client.return_value = mock_cosmos_instance

    # Call the method
    client = DatabaseFactory.get_conversation_client()

    # Assert the CosmosConversationClient was called with correct arguments
    mock_cosmos_client.assert_called_once_with(
        cosmosdb_endpoint="https://cosmos_account.documents.azure.com:443/",
        credential=mock_credential_instance,
        database_name="cosmos_database",
        container_name="conversations_container",
        enable_message_feedback=False,
    )
    assert isinstance(client, CosmosConversationClient)
    assert client == mock_cosmos_instance


@patch("backend.batch.utilities.chat_history.database_factory.DefaultAzureCredential")
@patch("backend.batch.utilities.chat_history.database_factory.EnvHelper")
@patch(
    "backend.batch.utilities.chat_history.database_factory.PostgresConversationClient",
    autospec=True,
)
def test_get_conversation_client_postgres(
    mock_postgres_client, mock_env_helper, mock_credential
):
    mock_env_instance = mock_env_helper.return_value
    mock_env_instance.DATABASE_TYPE = DatabaseType.POSTGRESQL.value
    mock_env_instance.POSTGRESQL_USER = "postgres_user"
    mock_env_instance.POSTGRESQL_HOST = "postgres_host"
    mock_env_instance.POSTGRESQL_DATABASE = "postgres_database"

    mock_access_token = MagicMock()
    mock_access_token.token = "mock-access-token"
    mock_credential.return_value.get_token.return_value = mock_access_token

    mock_postgres_instance = MagicMock(spec=PostgresConversationClient)
    mock_postgres_client.return_value = mock_postgres_instance

    client = DatabaseFactory.get_conversation_client()

    mock_postgres_client.assert_called_once_with(
        user="postgres_user", host="postgres_host", database="postgres_database"
    )
    assert isinstance(client, PostgresConversationClient)


@patch("backend.batch.utilities.chat_history.database_factory.EnvHelper")
def test_get_conversation_client_invalid_database_type(mock_env_helper):
    mock_env_instance = mock_env_helper.return_value
    mock_env_instance.DATABASE_TYPE = "INVALID_DB"

    with pytest.raises(ValueError, match="Unsupported DATABASE_TYPE"):
        DatabaseFactory.get_conversation_client()
