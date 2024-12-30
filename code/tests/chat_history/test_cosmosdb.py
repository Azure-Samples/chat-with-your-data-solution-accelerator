import pytest
from unittest.mock import AsyncMock, patch
from azure.cosmos import exceptions
from backend.batch.utilities.chat_history.cosmosdb import CosmosConversationClient


@pytest.fixture
def mock_cosmos_client():
    mock_client = AsyncMock()
    mock_database_client = AsyncMock()
    mock_container_client = AsyncMock()

    mock_client.get_database_client.return_value = mock_database_client
    mock_database_client.get_container_client.return_value = mock_container_client

    return mock_client, mock_database_client, mock_container_client


@pytest.fixture
def cosmos_client(mock_cosmos_client):
    cosmosdb_client, database_client, container_client = mock_cosmos_client
    with patch("azure.cosmos.aio.CosmosClient", return_value=cosmosdb_client):
        client = CosmosConversationClient(
            cosmosdb_endpoint="https://test-cosmosdb.com",
            credential="test-credential",
            database_name="test-database",
            container_name="test-container",
        )
        client.cosmosdb_client = cosmosdb_client
        client.database_client = database_client
        client.container_client = container_client
        return client


@pytest.mark.asyncio
async def test_initialize_client_success(cosmos_client):
    client = cosmos_client

    assert client.cosmosdb_endpoint == "https://test-cosmosdb.com"
    assert client.credential == "test-credential"
    assert client.database_name == "test-database"
    assert client.container_name == "test-container"


@pytest.mark.asyncio
async def test_ensure_client_initialized_success(cosmos_client):
    client = cosmos_client
    client.database_client.read = AsyncMock()
    client.container_client.read = AsyncMock()

    result, message = await client.ensure()

    assert result is True
    assert message == "CosmosDB client initialized successfully"
    client.database_client.read.assert_called_once()
    client.container_client.read.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_client_not_initialized(cosmos_client):
    client = cosmos_client
    client.database_client.read = AsyncMock(
        side_effect=exceptions.CosmosHttpResponseError
    )
    client.container_client.read = AsyncMock()

    result, message = await client.ensure()

    assert result is False
    assert "not found" in message.lower()
    client.database_client.read.assert_called_once()


@pytest.mark.asyncio
async def test_create_conversation_success(cosmos_client):
    client = cosmos_client
    client.container_client.upsert_item = AsyncMock(
        return_value={"id": "500e77bd-26b9-441a-8fe3-cd0e02993671"}
    )

    response = await client.create_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671", "Test Conversation"
    )

    assert response["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"


@pytest.mark.asyncio
async def test_create_conversation_failure(cosmos_client):
    client = cosmos_client
    client.container_client.upsert_item = AsyncMock(return_value=None)

    response = await client.create_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671", "Test Conversation"
    )

    assert response is False


@pytest.mark.asyncio
async def test_upsert_conversation_success(cosmos_client):
    client = cosmos_client
    client.container_client.upsert_item = AsyncMock(
        return_value={"id": "500e77bd-26b9-441a-8fe3-cd0e02993671"}
    )

    conversation = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "userId": "user-123",
        "title": "Updated Conversation",
    }
    response = await client.upsert_conversation(conversation)

    assert response["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"


@pytest.mark.asyncio
async def test_delete_conversation_success(cosmos_client):
    client = cosmos_client
    client.container_client.read_item = AsyncMock(
        return_value={"id": "500e77bd-26b9-441a-8fe3-cd0e02993671"}
    )
    client.container_client.delete_item = AsyncMock(return_value={"status": "deleted"})

    response = await client.delete_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671"
    )

    assert response["status"] == "deleted"
    client.container_client.delete_item.assert_called_once_with(
        item="500e77bd-26b9-441a-8fe3-cd0e02993671", partition_key="user-123"
    )


@pytest.mark.asyncio
async def test_delete_messages_success(cosmos_client):
    client = cosmos_client
    client.get_messages = AsyncMock(
        return_value=[
            {"id": "39c395da-e2f7-49c9-bca5-c9511d3c5172"},
            {"id": "39c395da-e2f7-49c9-bca5-c9511d3c5174"},
        ]
    )
    client.container_client.delete_item = AsyncMock()

    response = await client.delete_messages(
        "500e77bd-26b9-441a-8fe3-cd0e02993671", "user-123"
    )

    assert len(response) == 2
    client.get_messages.assert_called_once_with(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671"
    )
    client.container_client.delete_item.assert_any_call(
        item="39c395da-e2f7-49c9-bca5-c9511d3c5172", partition_key="user-123"
    )
    client.container_client.delete_item.assert_any_call(
        item="39c395da-e2f7-49c9-bca5-c9511d3c5174", partition_key="user-123"
    )


@pytest.mark.asyncio
async def test_update_message_feedback_success(cosmos_client):
    client = cosmos_client
    client.container_client.read_item = AsyncMock(
        return_value={"id": "39c395da-e2f7-49c9-bca5-c9511d3c5172", "feedback": ""}
    )
    client.container_client.upsert_item = AsyncMock(
        return_value={
            "id": "39c395da-e2f7-49c9-bca5-c9511d3c5172",
            "feedback": "positive",
        }
    )

    response = await client.update_message_feedback(
        "user-123", "39c395da-e2f7-49c9-bca5-c9511d3c5172", "positive"
    )

    assert response["feedback"] == "positive"
    client.container_client.upsert_item.assert_called_once()
