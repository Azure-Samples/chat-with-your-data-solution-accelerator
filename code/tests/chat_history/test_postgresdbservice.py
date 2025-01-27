import pytest
from unittest.mock import AsyncMock, patch
from backend.batch.utilities.chat_history.postgresdbservice import (
    PostgresConversationClient,
)


@pytest.fixture
def postgres_client():
    return PostgresConversationClient(
        user="test_user",
        host="test_host",
        database="test_db",
        enable_message_feedback=True,
    )


@pytest.fixture
def mock_connection():
    return AsyncMock()


@patch("backend.batch.utilities.chat_history.postgresdbservice.asyncpg.connect")
@patch("backend.batch.utilities.chat_history.postgresdbservice.DefaultAzureCredential")
@pytest.mark.asyncio
async def test_connect(mock_credential, mock_connect, postgres_client, mock_connection):
    # Mock DefaultAzureCredential
    mock_credential.return_value.get_token.return_value.token = "mock_token"

    # Mock asyncpg connection
    mock_connect.return_value = mock_connection

    # Test the connect method
    await postgres_client.connect()

    mock_connect.assert_called_once_with(
        user="test_user",
        host="test_host",
        database="test_db",
        password="mock_token",
        port=5432,
        ssl="require",
    )
    assert postgres_client.conn == mock_connection


@pytest.mark.asyncio
async def test_close(postgres_client, mock_connection):
    # Set up the connection
    postgres_client.conn = mock_connection

    # Test the close method
    await postgres_client.close()
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_not_initialized(postgres_client):
    postgres_client.conn = None
    result = await postgres_client.ensure()
    assert result == (False, "PostgreSQL client not initialized correctly")


@pytest.mark.asyncio
async def test_ensure_initialized(postgres_client, mock_connection):
    postgres_client.conn = mock_connection
    result = await postgres_client.ensure()
    assert result == (True, "PostgreSQL client initialized successfully")


@pytest.mark.asyncio
async def test_create_conversation(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetchrow return value
    mock_connection.fetchrow.return_value = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "user_id": "user_id",
        "title": "test_title",
    }

    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    user_id = "user_id"
    title = "test_title"
    result = await postgres_client.create_conversation(conversation_id, user_id, title)
    assert result["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"
    assert result["title"] == "test_title"


@pytest.mark.asyncio
async def test_upsert_conversation(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetchrow return value
    mock_connection.fetchrow.return_value = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-02T00:00:00.000Z",
        "user_id": "user_id",
        "title": "updated_title",
    }

    conversation = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-02T00:00:00.000Z",
        "user_id": "user_id",
        "title": "updated_title",
    }

    result = await postgres_client.upsert_conversation(conversation)

    assert result["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"
    assert result["title"] == "updated_title"


@pytest.mark.asyncio
async def test_delete_conversation(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    user_id = "user_id"
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    await postgres_client.delete_conversation(user_id, conversation_id)

    mock_connection.execute.assert_called_once_with(
        "DELETE FROM conversations WHERE conversation_id = $1 AND user_id = $2",
        conversation_id,
        user_id,
    )


@pytest.mark.asyncio
async def test_delete_messages(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetch return value
    mock_connection.fetch.return_value = [
        {
            "id": "39c395da-e2f7-49c9-bca5-c9511d3c5172",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "user_id": "user_id",
            "content": "Message 1 content",
        },
        {
            "id": "39c395da-e2f7-49c9-bca5-c9511d3c5173",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "user_id": "user_id",
            "content": "Message 2 content",
        },
    ]

    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    user_id = "user_id"
    result = await postgres_client.delete_messages(conversation_id, user_id)

    assert len(result) == 2
    assert result[0]["id"] == "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    mock_connection.fetch.assert_called_once_with(
        "DELETE FROM messages WHERE conversation_id = $1 AND user_id = $2 RETURNING *",
        conversation_id,
        user_id,
    )


@pytest.mark.asyncio
async def test_get_conversations(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetch return value
    mock_connection.fetch.return_value = [
        {
            "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "type": "conversation",
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-01T00:00:00.000Z",
            "user_id": "user_id",
            "title": "title1",
        },
        {
            "id": "500e77bd-26b9-441a-8fe3-cd0e02993672",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993672",
            "type": "conversation",
            "createdAt": "2024-01-02T00:00:00.000Z",
            "updatedAt": "2024-01-02T00:00:00.000Z",
            "user_id": "user_id",
            "title": "title2",
        },
    ]

    user_id = "user_id"
    result = await postgres_client.get_conversations(
        user_id, limit=2, sort_order="ASC", offset=0
    )

    assert len(result) == 2
    assert result[0]["title"] == "title1"
    assert result[1]["title"] == "title2"


@pytest.mark.asyncio
async def test_get_conversation(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetchrow return value
    mock_connection.fetchrow.return_value = {
        "id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "type": "conversation",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "user_id": "user_id",
        "title": "test_title",
    }

    user_id = "user_id"
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    result = await postgres_client.get_conversation(user_id, conversation_id)

    assert result["id"] == "500e77bd-26b9-441a-8fe3-cd0e02993671"
    assert result["title"] == "test_title"


@pytest.mark.asyncio
async def test_create_message(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetchrow return value
    mock_connection.fetchrow.return_value = {
        "id": "39c395da-e2f7-49c9-bca5-c9511d3c5172",
        "type": "message",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "user_id": "user_id",
        "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
        "role": "user",
        "content": "Test content",
        "feedback": "",
    }

    uuid = "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    user_id = "user_id"
    input_message = {"role": "user", "content": "Test content"}

    result = await postgres_client.create_message(
        uuid, conversation_id, user_id, input_message
    )

    assert result["id"] == "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    assert result["content"] == "Test content"
    mock_connection.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_message_feedback(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetchrow return value
    mock_connection.fetchrow.return_value = {
        "id": "39c395da-e2f7-49c9-bca5-c9511d3c5172",
        "user_id": "user_id",
        "feedback": "positive",
    }

    message_id = "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    user_id = "user_id"
    feedback = "positive"
    result = await postgres_client.update_message_feedback(
        user_id, message_id, feedback
    )

    assert result["feedback"] == "positive"
    mock_connection.fetchrow.assert_called_once_with(
        "UPDATE messages SET feedback = $1 WHERE id = $2 AND user_id = $3 RETURNING *",
        feedback,
        message_id,
        user_id,
    )


@pytest.mark.asyncio
async def test_get_messages(postgres_client, mock_connection):
    postgres_client.conn = mock_connection

    # Mock fetch return value
    mock_connection.fetch.return_value = [
        {
            "id": "39c395da-e2f7-49c9-bca5-c9511d3c5172",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "user_id": "user_id",
            "content": "Message 1 content",
        },
        {
            "id": "39c395da-e2f7-49c9-bca5-c9511d3c5173",
            "conversation_id": "500e77bd-26b9-441a-8fe3-cd0e02993671",
            "user_id": "user_id",
            "content": "Message 2 content",
        },
    ]

    user_id = "user_id"
    conversation_id = "500e77bd-26b9-441a-8fe3-cd0e02993671"
    result = await postgres_client.get_messages(user_id, conversation_id)

    assert len(result) == 2
    assert result[0]["id"] == "39c395da-e2f7-49c9-bca5-c9511d3c5172"
    assert result[1]["id"] == "39c395da-e2f7-49c9-bca5-c9511d3c5173"
