"""
This module tests the entry point for the application.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from create_app import create_app


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


class TestListConversations:
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
