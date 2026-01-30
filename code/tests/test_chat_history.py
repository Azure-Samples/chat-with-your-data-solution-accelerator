"""
This module contains comprehensive unit tests for the chat history API endpoints
and related helper functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from create_app import create_app
from backend.api.chat_history import (
    init_database_client,
    init_openai_client,
    generate_title,
)


@pytest.fixture
def client():
    """Create a test client for the app."""
    app = create_app()
    app.testing = True
    return app.test_client()


@pytest.fixture
def mock_conversation_client():
    """Mock the database client."""
    with patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    ) as mock:
        mock_conversation_client = AsyncMock()
        mock.return_value = mock_conversation_client
        yield mock_conversation_client


class TestChatHistory:
    # ============================================================================
    # Tests for init_database_client (helper function)
    # ============================================================================
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_init_database_client_success(self, mock_db_factory):
        """Test init_database_client successfully returns client."""
        # Given
        mock_client = MagicMock()
        mock_db_factory.return_value = mock_client

        # When
        result = init_database_client()

        # Then
        assert result == mock_client

    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_init_database_client_exception(self, mock_db_factory):
        """Test init_database_client raises exception on failure."""
        # Given
        mock_db_factory.side_effect = Exception("Database error")

        # When/Then
        with pytest.raises(Exception) as exc_info:
            init_database_client()
        assert str(exc_info.value) == "Database error"

    # ============================================================================
    # Tests for init_openai_client (helper function)
    # ============================================================================
    @patch("backend.api.chat_history.env_helper")
    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    def test_init_openai_client_with_keys(self, mock_azure_openai, mock_env):
        """Test init_openai_client with API key authentication."""
        # Given
        mock_env.is_auth_type_keys.return_value = True
        mock_env.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        mock_env.AZURE_OPENAI_API_VERSION = "2024-02-01"
        mock_env.AZURE_OPENAI_API_KEY = "test-key"

        # When
        result = init_openai_client()

        # Then
        assert result is not None
        mock_azure_openai.assert_called_once()

    @patch("backend.api.chat_history.env_helper")
    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    def test_init_openai_client_with_token(self, mock_azure_openai, mock_env):
        """Test init_openai_client with token provider authentication."""
        # Given
        mock_env.is_auth_type_keys.return_value = False
        mock_env.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        mock_env.AZURE_OPENAI_API_VERSION = "2024-02-01"
        mock_env.AZURE_TOKEN_PROVIDER = MagicMock()

        # When
        result = init_openai_client()

        # Then
        assert result is not None
        mock_azure_openai.assert_called_once()

    @patch("backend.api.chat_history.env_helper")
    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    def test_init_openai_client_exception(self, mock_azure_openai, mock_env):
        """Test init_openai_client raises exception on failure."""
        # Given
        mock_env.is_auth_type_keys.side_effect = Exception("Auth error")

        # When/Then
        with pytest.raises(Exception) as exc_info:
            init_openai_client()
        assert str(exc_info.value) == "Auth error"

    # ============================================================================
    # Tests for list_conversations endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_list_conversations_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the list_conversations endpoint works when everything is set up correctly."""
        # Given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        get_active_config_or_default_mock.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            return_value=[{"conversation_id": "1", "content": "Hello, world!"}]
        )

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 200
        assert response.json == [{"conversation_id": "1", "content": "Hello, world!"}]

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_list_conversations_no_history(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the list_conversations endpoint returns an error if chat history is not enabled."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = False

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_list_conversations_db_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the list_conversations endpoint returns an error if the database is not available."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            side_effect=Exception("Database error")
        )

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 500
        assert response.json == {
            "error": "Error while listing historical conversations"
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_list_conversations_no_conversations(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the list_conversations endpoint returns an error if no conversations are found."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            return_value="invalid response"
        )

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 404
        assert response.json == {
            "error": "No conversations for 00000000-0000-0000-0000-000000000000 were found"
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_list_conversations_with_custom_offset(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test list_conversations with custom offset parameter."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_client = AsyncMock()
        mock_db_factory.return_value = mock_client
        mock_client.get_conversations = AsyncMock(
            return_value=[{"conversation_id": "2", "content": "Page 2"}]
        )

        # When
        response = client.get("/api/history/list?offset=25")

        # Then
        assert response.status_code == 200
        mock_client.get_conversations.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_list_conversations_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test list_conversations when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_list_conversations_empty_list(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test list_conversations returns empty list successfully."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(return_value=[])

        # When
        response = client.get("/api/history/list?offset=0")

        # Then
        assert response.status_code == 200
        assert response.json == []

    # ============================================================================
    # Tests for rename_conversation endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the rename_conversation endpoint works correctly."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            return_value={"conversation_id": "1", "title": "Old Title"}
        )
        mock_conversation_client.upsert_conversation = AsyncMock(
            return_value={"conversation_id": "1", "title": "New Title"}
        )

        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 200
        assert response.json == {"conversation_id": "1", "title": "New Title"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_no_history(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the rename_conversation endpoint returns an error if chat history is not enabled."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = False

        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_missing_conversation_id(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the rename_conversation endpoint returns an error if conversation_id is missing."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        request_json = {"title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "conversation_id is required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_empty_title(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the rename_conversation endpoint returns an error if the title is empty."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        request_json = {"conversation_id": "1", "title": ""}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "A non-empty title is required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_rename_conversation_db_error(
        self, mock_conversation_client, get_active_config_or_default_mock, client
    ):
        """Test that the rename_conversation endpoint returns an error if the database is not available."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.return_value.get_conversation = AsyncMock(
            side_effect=Exception("Database error")
        )

        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while renaming conversation"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_not_found(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the rename_conversation endpoint returns an error if the conversation is not found."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(return_value=None)

        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {
            "error": "Conversation 1 was not found. It either does not exist or the logged in user does not have access to it."
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_whitespace_only_title(
        self, get_active_config_or_default_mock, client
    ):
        """Test rename_conversation with whitespace-only title."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        request_json = {"conversation_id": "1", "title": "   "}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "A non-empty title is required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_rename_conversation_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test rename_conversation when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None
        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_rename_conversation_upsert_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test rename_conversation when upsert fails."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"conversation_id": "1", "title": "Old Title"}
        )
        mock_conversation_client.upsert_conversation = AsyncMock(
            side_effect=Exception("Upsert failed")
        )
        request_json = {"conversation_id": "1", "title": "New Title"}

        # When
        response = client.post("/api/history/rename", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while renaming conversation"}

    # ============================================================================
    # Tests for get_conversation endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the get_conversation endpoint works correctly."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"conversation_id": "1", "title": "Sample Conversation"}
        )
        mock_conversation_client.get_messages = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "role": "user",
                    "content": "Hello, world!",
                    "createdAt": "2024-11-29T12:00:00Z",
                }
            ]
        )

        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 200
        assert response.json == {
            "conversation_id": "1",
            "messages": [
                {
                    "id": "1",
                    "role": "user",
                    "content": "Hello, world!",
                    "createdAt": "2024-11-29T12:00:00Z",
                    "feedback": None,
                }
            ],
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_no_history(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the get_conversation endpoint returns an error if chat history is not enabled."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = False

        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_missing_conversation_id(
        self, get_active_config_or_default_mock, client
    ):
        """Test that the get_conversation endpoint returns an error if conversation_id is missing."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        request_json = {}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "conversation_id is required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_get_conversation_db_error(
        self, mock_conversation_client, get_active_config_or_default_mock, client
    ):
        """Test that the get_conversation endpoint returns an error if the database is not available."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.return_value.get_conversation = AsyncMock(
            side_effect=Exception("Database error")
        )

        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while fetching conversation history"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_not_found(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the get_conversation endpoint returns an error if the conversation is not found."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(return_value=None)

        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {
            "error": "Conversation 1 was not found. It either does not exist or the logged in user does not have access to it."
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_get_conversation_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test get_conversation when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None
        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_with_feedback(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test get_conversation with messages that have feedback."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"conversation_id": "1", "title": "Test"}
        )
        mock_conversation_client.get_messages = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "role": "user",
                    "content": "Hello",
                    "createdAt": "2024-11-29T12:00:00Z",
                    "feedback": "positive",
                }
            ]
        )
        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 200
        assert response.json["messages"][0]["feedback"] == "positive"

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_conversation_get_messages_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test get_conversation when fetching messages fails."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"conversation_id": "1", "title": "Test"}
        )
        mock_conversation_client.get_messages = AsyncMock(
            side_effect=Exception("Failed to fetch messages")
        )
        request_json = {"conversation_id": "1"}

        # When
        response = client.post("/api/history/read", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while fetching conversation history"}

    # ============================================================================
    # Tests for delete_conversation endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test that the delete_conversation endpoint works correctly."""

        # Setup mocks
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        # Mock the database client
        mock_conversation_client.delete_messages = AsyncMock(return_value=None)
        mock_conversation_client.delete_conversation = AsyncMock(return_value=None)

        # Define request data
        request_json = {"conversation_id": "conv123"}

        # Make DELETE request to delete the conversation
        response = client.delete("/api/history/delete", json=request_json)

        # Assert the response status and data
        assert response.status_code == 200
        assert response.json == {
            "message": "Successfully deleted conversation and messages",
            "conversation_id": "conv123",
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_no_chat_history(
        self, get_active_config_or_default_mock, client
    ):
        """Test when chat history is not enabled in the configuration."""

        # Setup mocks
        get_active_config_or_default_mock.return_value.enable_chat_history = False

        # Define request data
        request_json = {"conversation_id": "conv123"}

        # Make DELETE request to delete the conversation
        response = client.delete("/api/history/delete", json=request_json)

        # Assert the response status and error message
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_missing_conversation_id(
        self, get_active_config_or_default_mock, client
    ):
        """Test when the conversation_id is missing in the request."""

        # Setup mocks
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        # Define request data (missing conversation_id)
        request_json = {}

        # Make DELETE request to delete the conversation
        response = client.delete("/api/history/delete", json=request_json)

        # Assert the response status and error message
        assert response.status_code == 400
        assert response.json == {
            "error": "Conversation None was not found. It either does not exist or the logged in user does not have access to it."
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_database_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test when the database client connection fails."""

        # Setup mocks
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        # Mock a failure in the database client connection
        mock_conversation_client.connect.side_effect = Exception(
            "Database not available"
        )

        # Define request data
        request_json = {"conversation_id": "conv123"}

        # Make DELETE request to delete the conversation
        response = client.delete("/api/history/delete", json=request_json)

        # Assert the response status and error message
        assert response.status_code == 500
        assert response.json == {"error": "Error while deleting conversation history"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_internal_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test when an unexpected internal error occurs during conversation deletion."""

        # Setup mocks
        get_active_config_or_default_mock.return_value.enable_chat_history = True

        # Mock an unexpected error in the database client deletion
        mock_conversation_client.delete_messages.side_effect = Exception(
            "Unexpected error"
        )

        # Define request data
        request_json = {"conversation_id": "conv123"}

        # Make DELETE request to delete the conversation
        response = client.delete("/api/history/delete", json=request_json)

        # Assert the response status and error message
        assert response.status_code == 500
        assert response.json == {"error": "Error while deleting conversation history"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_delete_conversation_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test delete_conversation when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None
        request_json = {"conversation_id": "conv123"}

        # When
        response = client.delete("/api/history/delete", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_conversation_delete_conversation_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test delete_conversation when deleting conversation fails."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.delete_messages = AsyncMock(return_value=None)
        mock_conversation_client.delete_conversation = AsyncMock(
            side_effect=Exception("Failed to delete conversation")
        )
        request_json = {"conversation_id": "conv123"}

        # When
        response = client.delete("/api/history/delete", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while deleting conversation history"}

    # ============================================================================
    # Tests for delete_all_conversations endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_all_conversations_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value=[{"id": "conv1"}, {"id": "conv2"}]
        )

        response = client.delete("/api/history/delete_all")
        assert response.status_code == 200
        assert response.json == {
            "message": "Successfully deleted all conversations and messages for user 00000000-0000-0000-0000-000000000000"
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_all_conversations_no_chat_history(
        self, get_active_config_or_default_mock, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = False
        response = client.delete("/api/history/delete_all")
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_delete_all_conversations_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test delete_all_conversations when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None

        # When
        response = client.delete("/api/history/delete_all")

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_all_conversations_no_conversations_found(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test delete_all_conversations when no conversations exist."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(return_value=None)

        # When
        response = client.delete("/api/history/delete_all")

        # Then
        assert response.status_code == 400
        assert "No conversations found" in response.json["error"]

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_all_conversations_partial_failure(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test delete_all_conversations continues when individual deletions fail."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            return_value=[{"id": "conv1"}, {"id": "conv2"}, {"id": "conv3"}]
        )
        # Make the second deletion fail
        mock_conversation_client.delete_messages = AsyncMock(
            side_effect=[None, Exception("Failed"), None]
        )
        mock_conversation_client.delete_conversation = AsyncMock(return_value=None)

        # When
        response = client.delete("/api/history/delete_all")

        # Then - Should still succeed for other conversations
        assert response.status_code == 200
        assert "Successfully deleted all conversations" in response.json["message"]

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_delete_all_conversations_get_conversations_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test delete_all_conversations when fetching conversations fails."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversations = AsyncMock(
            side_effect=Exception("Failed to fetch conversations")
        )

        # When
        response = client.delete("/api/history/delete_all")

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Error while deleting all conversation history"}

    # ============================================================================
    # Tests for update_conversation endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_success(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation.return_value = {
            "title": "Test Title",
            "updatedAt": "2024-12-01",
            "id": "conv1",
        }
        mock_conversation_client.create_message.return_value = "success"
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        assert response.status_code == 200
        assert response.json == {
            "data": {
                "conversation_id": "conv1",
                "date": "2024-12-01",
                "title": "Test Title",
            },
            "success": True,
        }

    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_new_success(
        self,
        get_active_config_or_default_mock,
        azure_openai_mock: MagicMock,
        mock_conversation_client,
        client,
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation.return_value = []
        mock_conversation_client.create_message.return_value = "success"
        mock_conversation_client.create_conversation.return_value = {
            "title": "Test Title",
            "updatedAt": "2024-12-01",
            "id": "conv1",
        }
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        openai_client_mock = azure_openai_mock.return_value

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test Title"))]

        openai_client_mock.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        response = client.post("/api/history/update", json=request_json)

        assert response.status_code == 200
        assert response.json == {
            "data": {
                "conversation_id": "conv1",
                "date": "2024-12-01",
                "title": "Test Title",
            },
            "success": True,
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_no_chat_history(
        self, get_active_config_or_default_mock, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = False
        response = client.post(
            "/api/history/update", json={}, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert response.json == {"error": "Chat history is not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_connect_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation.return_value = {
            "title": "Test Title",
            "updatedAt": "2024-12-01",
            "id": "conv1",
        }
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }
        mock_conversation_client.connect.side_effect = Exception("Unexpected error")

        # Make the API call
        response = client.post(
            "/api/history/update",
            json=request_json,
            headers={"Content-Type": "application/json"},
        )

        # Assert response
        assert response.status_code == 500
        assert response.json == {
            "error": "Error while updating the conversation history"
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_error(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.create_message.side_effect = Exception(
            "Unexpected error"
        )
        mock_conversation_client.get_conversation.return_value = {
            "title": "Test Title",
            "updatedAt": "2024-12-01",
            "id": "conv1",
        }
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        response = client.post(
            "/api/history/update",
            json=request_json,
            headers={"Content-Type": "application/json"},
        )

        # Assert response
        assert response.status_code == 500
        assert response.json == {
            "error": "Error while updating the conversation history"
        }

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_missing_conversation_id(
        self, get_active_config_or_default_mock, client
    ):
        """Test update_conversation with missing conversation_id."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        request_json = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "conversation_id is required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_missing_messages(
        self, get_active_config_or_default_mock, client
    ):
        """Test update_conversation with missing messages."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        request_json = {"conversation_id": "conv1", "messages": []}

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "Messages are required"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.chat_history.database_factory.DatabaseFactory.get_conversation_client"
    )
    def test_update_conversation_database_not_available(
        self, mock_db_factory, get_active_config_or_default_mock, client
    ):
        """Test update_conversation when database client is None."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_db_factory.return_value = None
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 500
        assert response.json == {"error": "Database not available"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_only_assistant_messages(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test update_conversation when there are only assistant messages (no user messages)."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"title": "Test", "updatedAt": "2024-12-01", "id": "conv1"}
        )
        mock_conversation_client.create_message = AsyncMock(return_value="success")
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "assistant", "content": "Hi!"},
                {"role": "assistant", "content": "How can I help?"},
            ],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        # The code searches in reverse for user messages - if none found, still succeeds
        # because messages[0]["role"] != "user", so user message processing is skipped
        assert response.status_code == 200

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_no_assistant_message(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test update_conversation when no assistant message is found."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"title": "Test", "updatedAt": "2024-12-01", "id": "conv1"}
        )
        mock_conversation_client.create_message = AsyncMock(return_value="success")
        request_json = {
            "conversation_id": "conv1",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "No assistant message found"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_with_tool_message(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test update_conversation with tool message before assistant message."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"title": "Test", "updatedAt": "2024-12-01", "id": "conv1"}
        )
        mock_conversation_client.create_message = AsyncMock(return_value="success")
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "tool", "content": "Tool output"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 200
        # Verify tool message was created first
        assert mock_conversation_client.create_message.call_count >= 2

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_update_conversation_create_message_not_found(
        self, get_active_config_or_default_mock, mock_conversation_client, client
    ):
        """Test update_conversation when conversation is not found during message creation."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        mock_conversation_client.get_conversation = AsyncMock(
            return_value={"title": "Test", "updatedAt": "2024-12-01", "id": "conv1"}
        )
        mock_conversation_client.create_message = AsyncMock(
            return_value="Conversation not found"
        )
        request_json = {
            "conversation_id": "conv1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        }

        # When
        response = client.post("/api/history/update", json=request_json)

        # Then
        assert response.status_code == 400
        assert response.json == {"error": "Conversation not found"}

    # ============================================================================
    # Tests for get_frontend_settings endpoint
    # ============================================================================
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_frontend_settings_success(
        self, get_active_config_or_default_mock, client
    ):
        get_active_config_or_default_mock.return_value.enable_chat_history = True
        response = client.get("/api/history/frontend_settings")
        assert response.status_code == 200
        assert response.json == {"CHAT_HISTORY_ENABLED": True}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_frontend_settings_error(
        self, get_active_config_or_default_mock, client
    ):
        get_active_config_or_default_mock.side_effect = Exception("Test Error")
        response = client.get("/api/history/frontend_settings")
        assert response.status_code == 500
        assert response.json == {"error": "Error while getting frontend settings"}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_frontend_settings_string_true(
        self, get_active_config_or_default_mock, client
    ):
        """Test frontend_settings with string 'true' value."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = "true"

        # When
        response = client.get("/api/history/frontend_settings")

        # Then
        assert response.status_code == 200
        assert response.json == {"CHAT_HISTORY_ENABLED": True}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_frontend_settings_string_false(
        self, get_active_config_or_default_mock, client
    ):
        """Test frontend_settings with string 'false' value."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = "false"

        # When
        response = client.get("/api/history/frontend_settings")

        # Then
        assert response.status_code == 200
        assert response.json == {"CHAT_HISTORY_ENABLED": False}

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_get_frontend_settings_boolean_false(
        self, get_active_config_or_default_mock, client
    ):
        """Test frontend_settings with boolean False value."""
        # Given
        get_active_config_or_default_mock.return_value.enable_chat_history = False

        # When
        response = client.get("/api/history/frontend_settings")

        # Then
        assert response.status_code == 200
        assert response.json == {"CHAT_HISTORY_ENABLED": False}

    # ============================================================================
    # Tests for generate_title (helper function)
    # ============================================================================
    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @pytest.mark.asyncio
    async def test_generate_title_success(self, azure_openai_mock):
        """Test generate_title successfully generates a title."""
        # Given
        messages = [
            {"role": "user", "content": "What is the weather?"},
            {"role": "assistant", "content": "It's sunny today"},
        ]

        openai_client_mock = azure_openai_mock.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Weather Query"))]
        openai_client_mock.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        # When
        title = await generate_title(messages)

        # Then
        assert title == "Weather Query"

    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @pytest.mark.asyncio
    async def test_generate_title_no_choices(self, azure_openai_mock):
        """Test generate_title fallback when no choices in response."""
        # Given
        messages = [
            {"role": "user", "content": "What is the weather?"},
            {"role": "assistant", "content": "It's sunny today"},
        ]

        openai_client_mock = azure_openai_mock.return_value
        mock_response = MagicMock()
        mock_response.choices = []
        openai_client_mock.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        # When
        title = await generate_title(messages)

        # Then
        assert title == "What is the weather?"

    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @pytest.mark.asyncio
    async def test_generate_title_exception(self, azure_openai_mock):
        """Test generate_title fallback when exception occurs."""
        # Given
        messages = [
            {"role": "user", "content": "What is the weather?"},
        ]

        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        # When
        title = await generate_title(messages)

        # Then
        assert title == "What is the weather?"

    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @pytest.mark.asyncio
    async def test_generate_title_single_message(self, azure_openai_mock):
        """Test generate_title with single message fallback."""
        # Given
        messages = [{"role": "user", "content": "Hello"}]

        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        # When
        title = await generate_title(messages)

        # Then
        # After filtering user messages and appending prompt: [{Hello}, {prompt}]
        # messages[-2] = "Hello", so fallback returns "Hello"
        assert title == "Hello"

    @patch("backend.api.chat_history.AsyncAzureOpenAI")
    @pytest.mark.asyncio
    async def test_generate_title_no_user_messages(self, azure_openai_mock):
        """Test generate_title when there are no user messages."""
        # Given
        messages = [{"role": "assistant", "content": "Hello from assistant"}]

        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        # When
        title = await generate_title(messages)

        # Then
        # After filtering, only prompt remains: [{prompt}]
        # len(messages) == 1, so fallback returns "Untitled"
        assert title == "Untitled"
