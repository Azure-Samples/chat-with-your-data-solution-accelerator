import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


# Tests for __init__
@pytest.mark.asyncio
async def test_initialize_client_success(cosmos_client):
    client = cosmos_client

    assert client.cosmosdb_endpoint == "https://test-cosmosdb.com"
    assert client.credential == "test-credential"
    assert client.database_name == "test-database"
    assert client.container_name == "test-container"


def test_init_invalid_credentials():
    """Test initialization with invalid credentials"""
    with patch("backend.batch.utilities.chat_history.cosmosdb.CosmosClient") as mock_cosmos:
        error = exceptions.CosmosHttpResponseError(status_code=401)
        mock_cosmos.side_effect = error

        with pytest.raises(ValueError, match="Invalid credentials"):
            CosmosConversationClient(
                cosmosdb_endpoint="https://test-cosmosdb.com",
                credential="invalid-credential",
                database_name="test-database",
                container_name="test-container",
            )


def test_init_invalid_endpoint():
    """Test initialization with invalid endpoint"""
    with patch("backend.batch.utilities.chat_history.cosmosdb.CosmosClient") as mock_cosmos:
        error = exceptions.CosmosHttpResponseError(status_code=404)
        mock_cosmos.side_effect = error

        with pytest.raises(ValueError, match="Invalid CosmosDB endpoint"):
            CosmosConversationClient(
                cosmosdb_endpoint="https://invalid-endpoint.com",
                credential="test-credential",
                database_name="test-database",
                container_name="test-container",
            )


def test_init_invalid_database():
    """Test initialization with invalid database name"""
    with patch("backend.batch.utilities.chat_history.cosmosdb.CosmosClient") as mock_cosmos:
        mock_client = MagicMock()
        mock_client.get_database_client.side_effect = exceptions.CosmosResourceNotFoundError
        mock_cosmos.return_value = mock_client

        with pytest.raises(ValueError, match="Invalid CosmosDB database name"):
            CosmosConversationClient(
                cosmosdb_endpoint="https://test-cosmosdb.com",
                credential="test-credential",
                database_name="invalid-database",
                container_name="test-container",
            )


def test_init_invalid_container():
    """Test initialization with invalid container name"""
    with patch("backend.batch.utilities.chat_history.cosmosdb.CosmosClient") as mock_cosmos:
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_database.get_container_client.side_effect = exceptions.CosmosResourceNotFoundError
        mock_client.get_database_client.return_value = mock_database
        mock_cosmos.return_value = mock_client

        with pytest.raises(ValueError, match="Invalid CosmosDB container name"):
            CosmosConversationClient(
                cosmosdb_endpoint="https://test-cosmosdb.com",
                credential="test-credential",
                database_name="test-database",
                container_name="invalid-container",
            )


# Tests for ensure
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
async def test_ensure_client_not_initialized_none_client():
    """Test ensure when clients are None"""
    with patch("azure.cosmos.aio.CosmosClient") as mock_cosmos:
        mock_cosmos.return_value = AsyncMock()
        client = CosmosConversationClient(
            cosmosdb_endpoint="https://test-cosmosdb.com",
            credential="test-credential",
            database_name="test-database",
            container_name="test-container",
        )
        client.cosmosdb_client = None

        result, message = await client.ensure()

        assert result is False
        assert message == "CosmosDB client not initialized correctly"


@pytest.mark.asyncio
async def test_ensure_container_not_found(cosmos_client):
    """Test ensure when container read fails"""
    client = cosmos_client
    client.database_client.read = AsyncMock()
    client.container_client.read = AsyncMock(
        side_effect=exceptions.CosmosResourceNotFoundError
    )

    result, message = await client.ensure()

    assert result is False
    assert "container" in message.lower()
    assert "not found" in message.lower()


# Tests for create_conversation
@pytest.mark.asyncio
async def test_create_conversation_success(cosmos_client):
    """Test create_conversation creates proper conversation structure"""
    client = cosmos_client

    # Capture what was passed to upsert_item
    captured_conversation = None

    async def capture_upsert(item):
        nonlocal captured_conversation
        captured_conversation = item
        return item

    client.container_client.upsert_item = AsyncMock(side_effect=capture_upsert)

    response = await client.create_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671", "Test Conversation"
    )

    # Verify the conversation structure has all required fields
    assert captured_conversation["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"
    assert captured_conversation["type"] == "conversation"
    assert captured_conversation["userId"] == "user-123"
    assert captured_conversation["title"] == "Test Conversation"
    assert captured_conversation["conversationId"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"
    assert "createdAt" in captured_conversation
    assert "updatedAt" in captured_conversation
    assert response["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"


@pytest.mark.asyncio
async def test_create_conversation_failure(cosmos_client):
    client = cosmos_client
    client.container_client.upsert_item = AsyncMock(return_value=None)

    response = await client.create_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671", "Test Conversation"
    )

    assert response is False


# Tests for upsert_conversation
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
async def test_upsert_conversation_failure(cosmos_client):
    """Test upsert_conversation when it fails"""
    client = cosmos_client
    client.container_client.upsert_item = AsyncMock(return_value=None)

    conversation = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "userId": "user-123",
        "title": "Test Conversation",
    }
    response = await client.upsert_conversation(conversation)

    assert response is False


# Tests for delete_conversation
@pytest.mark.asyncio
async def test_delete_conversation_success(cosmos_client):
    """Test delete_conversation business logic: read first, then delete"""
    client = cosmos_client
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    user_id = "user-123"

    client.container_client.read_item = AsyncMock(
        return_value={"id": conversation_id}
    )
    client.container_client.delete_item = AsyncMock(return_value={"status": "deleted"})

    response = await client.delete_conversation(user_id, conversation_id)

    # Verify read was called first to check existence
    client.container_client.read_item.assert_called_once_with(
        item=conversation_id, partition_key=user_id
    )
    # Verify delete was called with correct parameters
    client.container_client.delete_item.assert_called_once_with(
        item=conversation_id, partition_key=user_id
    )
    assert response["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_conversation_not_found(cosmos_client):
    """Test delete_conversation returns True when conversation doesn't exist (idempotent behavior)"""
    client = cosmos_client
    client.container_client.read_item = AsyncMock(return_value=None)

    response = await client.delete_conversation(
        "user-123", "500e77bd-26b9-441a-8fe3-cd0e02993671"
    )

    # Business logic: should return True even when not found (idempotent)
    assert response is True
    # Verify delete was NOT called when item doesn't exist
    client.container_client.delete_item.assert_not_called()


# Tests for delete_messages
@pytest.mark.asyncio
async def test_delete_messages_success(cosmos_client):
    """Test delete_messages business logic: get messages, then delete each one"""
    client = cosmos_client
    msg1_id = "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    msg2_id = "39c395da-e2f7-49c9-bca5-c9511d3c5174"
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    user_id = "user-123"

    client.get_messages = AsyncMock(
        return_value=[
            {"id": msg1_id},
            {"id": msg2_id},
        ]
    )
    client.container_client.delete_item = AsyncMock()

    response = await client.delete_messages(conversation_id, user_id)

    # Verify get_messages was called first
    client.get_messages.assert_called_once_with(user_id, conversation_id)
    # Verify delete was called for each message
    assert len(response) == 2
    client.container_client.delete_item.assert_any_call(
        item=msg1_id, partition_key=user_id
    )
    client.container_client.delete_item.assert_any_call(
        item=msg2_id, partition_key=user_id
    )


@pytest.mark.asyncio
async def test_delete_messages_no_messages(cosmos_client):
    """Test delete_messages when no messages exist"""
    client = cosmos_client
    client.get_messages = AsyncMock(return_value=None)

    response = await client.delete_messages(
        "500e77bd-26b9-441a-8fe3-cd0e02993671", "user-123"
    )

    assert response is None


# Tests for get_conversations
@pytest.mark.asyncio
async def test_get_conversations(cosmos_client):
    """Test get_conversations method"""
    client = cosmos_client

    mock_conversations = [
        {
            "id": "conv1",
            "type": "conversation",
            "userId": "user-123",
            "title": "Conversation 1",
            "updatedAt": "2024-01-01T00:00:00",
        },
        {
            "id": "conv2",
            "type": "conversation",
            "userId": "user-123",
            "title": "Conversation 2",
            "updatedAt": "2024-01-02T00:00:00",
        },
    ]

    async def mock_query_items(query, parameters):
        for item in mock_conversations:
            yield item

    client.container_client.query_items = mock_query_items

    conversations = await client.get_conversations("user-123", limit=10, sort_order="DESC", offset=0)

    assert len(conversations) == 2
    assert conversations[0]["id"] == "conv1"
    assert conversations[1]["id"] == "conv2"


@pytest.mark.asyncio
async def test_get_conversations_no_limit(cosmos_client):
    """Test get_conversations with no limit"""
    client = cosmos_client

    mock_conversations = [
        {"id": "conv1", "type": "conversation", "userId": "user-123"},
    ]

    async def mock_query_items(query, parameters):
        for item in mock_conversations:
            yield item

    client.container_client.query_items = mock_query_items

    conversations = await client.get_conversations("user-123", limit=None)

    assert len(conversations) == 1


# Tests for get_conversation
@pytest.mark.asyncio
async def test_get_conversation(cosmos_client):
    """Test get_conversation method"""
    client = cosmos_client

    mock_conversation = {
        "id": "conv1",
        "type": "conversation",
        "userId": "user-123",
        "title": "Test Conversation",
    }

    async def mock_query_items(query, parameters):
        yield mock_conversation

    client.container_client.query_items = mock_query_items

    conversation = await client.get_conversation("user-123", "conv1")

    assert conversation is not None
    assert conversation["id"] == "conv1"


@pytest.mark.asyncio
async def test_get_conversation_not_found(cosmos_client):
    """Test get_conversation when conversation doesn't exist"""
    client = cosmos_client

    async def mock_query_items(query, parameters):
        return
        yield  # Make it an async generator

    client.container_client.query_items = mock_query_items

    conversation = await client.get_conversation("user-123", "nonexistent")

    assert conversation is None


# Tests for create_message
@pytest.mark.asyncio
async def test_create_message(cosmos_client):
    """Test create_message business logic: creates message and updates parent conversation timestamp"""
    client = cosmos_client

    captured_message = None
    captured_conversation = None

    async def capture_message_upsert(item):
        nonlocal captured_message
        captured_message = item
        return item

    async def capture_conversation_upsert(item):
        nonlocal captured_conversation
        captured_conversation = item
        return item

    mock_conversation = {
        "id": "conv1",
        "type": "conversation",
        "userId": "user-123",
        "updatedAt": "2024-01-01T00:00:00",
    }

    client.container_client.upsert_item = AsyncMock(side_effect=capture_message_upsert)
    client.get_conversation = AsyncMock(return_value=mock_conversation)
    client.upsert_conversation = AsyncMock(side_effect=capture_conversation_upsert)

    input_message = {"role": "user", "content": "Hello"}

    response = await client.create_message("msg1", "conv1", "user-123", input_message)

    # Verify message structure
    assert captured_message["id"] == "msg1"
    assert captured_message["type"] == "message"
    assert captured_message["userId"] == "user-123"
    assert captured_message["conversationId"] == "conv1"
    assert captured_message["role"] == "user"
    assert captured_message["content"] == "Hello"
    assert "createdAt" in captured_message
    assert "updatedAt" in captured_message

    # Verify business logic: conversation's updatedAt is set to message's createdAt
    client.get_conversation.assert_called_once_with("user-123", "conv1")
    assert captured_conversation["updatedAt"] == captured_message["createdAt"]
    client.upsert_conversation.assert_called_once()

    assert response["id"] == "msg1"


@pytest.mark.asyncio
async def test_create_message_with_feedback(cosmos_client):
    """Test create_message with feedback enabled adds feedback field to message"""
    with patch("azure.cosmos.aio.CosmosClient") as mock_cosmos:
        mock_client = AsyncMock()
        mock_database = AsyncMock()
        mock_container = AsyncMock()

        mock_client.get_database_client.return_value = mock_database
        mock_database.get_container_client.return_value = mock_container
        mock_cosmos.return_value = mock_client

        client = CosmosConversationClient(
            cosmosdb_endpoint="https://test-cosmosdb.com",
            credential="test-credential",
            database_name="test-database",
            container_name="test-container",
            enable_message_feedback=True,
        )

        client.cosmosdb_client = mock_client
        client.database_client = mock_database
        client.container_client = mock_container

        captured_message = None

        async def capture_upsert(item):
            nonlocal captured_message
            captured_message = item
            return item

        mock_conversation = {
            "id": "conv1",
            "type": "conversation",
            "userId": "user-123",
        }

        client.container_client.upsert_item = AsyncMock(side_effect=capture_upsert)
        client.get_conversation = AsyncMock(return_value=mock_conversation)
        client.upsert_conversation = AsyncMock()

        input_message = {"role": "user", "content": "Hello"}

        response = await client.create_message("msg1", "conv1", "user-123", input_message)

        # Verify business logic: feedback field is added when enabled
        assert "feedback" in captured_message
        assert captured_message["feedback"] == ""
        assert response["id"] == "msg1"


@pytest.mark.asyncio
async def test_create_message_conversation_not_found(cosmos_client):
    """Test create_message when conversation doesn't exist"""
    client = cosmos_client

    mock_message = {
        "id": "msg1",
        "type": "message",
        "userId": "user-123",
        "conversationId": "conv1",
        "role": "user",
        "content": "Hello",
    }

    client.container_client.upsert_item = AsyncMock(return_value=mock_message)
    client.get_conversation = AsyncMock(return_value=None)

    input_message = {"role": "user", "content": "Hello"}

    response = await client.create_message("msg1", "conv1", "user-123", input_message)

    assert response == "Conversation not found"


@pytest.mark.asyncio
async def test_create_message_failure(cosmos_client):
    """Test create_message when upsert fails"""
    client = cosmos_client

    client.container_client.upsert_item = AsyncMock(return_value=None)

    input_message = {"role": "user", "content": "Hello"}

    response = await client.create_message("msg1", "conv1", "user-123", input_message)

    assert response is False


# Tests for update_message_feedback
@pytest.mark.asyncio
async def test_update_message_feedback_success(cosmos_client):
    """Test update_message_feedback business logic: read message, update feedback, upsert"""
    client = cosmos_client
    message_id = "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    user_id = "user-123"

    original_message = {"id": message_id, "feedback": ""}

    captured_message = None

    async def capture_upsert(item):
        nonlocal captured_message
        captured_message = item
        return item

    client.container_client.read_item = AsyncMock(return_value=original_message)
    client.container_client.upsert_item = AsyncMock(side_effect=capture_upsert)

    response = await client.update_message_feedback(user_id, message_id, "positive")

    # Verify business logic: message was read, feedback updated, then upserted
    client.container_client.read_item.assert_called_once_with(
        item=message_id, partition_key=user_id
    )
    assert captured_message["feedback"] == "positive"
    client.container_client.upsert_item.assert_called_once()
    assert response["feedback"] == "positive"


@pytest.mark.asyncio
async def test_update_message_feedback_not_found(cosmos_client):
    """Test update_message_feedback when message doesn't exist"""
    client = cosmos_client
    client.container_client.read_item = AsyncMock(return_value=None)

    response = await client.update_message_feedback(
        "user-123", "nonexistent-msg", "positive"
    )

    assert response is False


# Tests for get_messages
@pytest.mark.asyncio
async def test_get_messages(cosmos_client):
    """Test get_messages method"""
    client = cosmos_client

    mock_messages = [
        {
            "id": "msg1",
            "type": "message",
            "conversationId": "conv1",
            "userId": "user-123",
            "content": "Hello",
        },
        {
            "id": "msg2",
            "type": "message",
            "conversationId": "conv1",
            "userId": "user-123",
            "content": "Hi there",
        },
    ]

    async def mock_query_items(query, parameters):
        for item in mock_messages:
            yield item

    client.container_client.query_items = mock_query_items

    messages = await client.get_messages("user-123", "conv1")

    assert len(messages) == 2
    assert messages[0]["id"] == "msg1"
    assert messages[1]["id"] == "msg2"
