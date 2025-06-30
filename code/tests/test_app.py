"""
This module tests the entry point for the application.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch, ANY

from openai import RateLimitError, BadRequestError, InternalServerError
import pytest
from flask.testing import FlaskClient
from backend.batch.utilities.helpers.config.conversation_flow import ConversationFlow
from create_app import create_app

AZURE_SPEECH_KEY = "mock-speech-key"
AZURE_SPEECH_SERVICE_REGION = "mock-speech-service-region"
AZURE_SPEECH_REGION_ENDPOINT = "mock-speech-region-endpoint"
AZURE_OPENAI_ENDPOINT = "mock-openai-endpoint"
AZURE_OPENAI_MODEL = "mock-openai-model"
AZURE_OPENAI_EMBEDDING_MODEL = "mock-openai-embedding-model"
AZURE_OPENAI_SYSTEM_MESSAGE = "system-message"
AZURE_OPENAI_API_VERSION = "mock-version"
AZURE_OPENAI_API_KEY = "mock-api-key"
AZURE_SEARCH_KEY = "mock-search-key"
AZURE_SEARCH_INDEX = "mock-search-index"
AZURE_SEARCH_SERVICE = "mock-search-service"
AZURE_SEARCH_CONTENT_COLUMN = "field1|field2"
AZURE_SEARCH_CONTENT_VECTOR_COLUMN = "vector-column"
AZURE_SEARCH_TITLE_COLUMN = "title"
AZURE_SEARCH_SOURCE_COLUMN = "source"
AZURE_SEARCH_TEXT_COLUMN = "text"
AZURE_SEARCH_LAYOUT_TEXT_COLUMN = "layoutText"
AZURE_SEARCH_FILENAME_COLUMN = "filename"
AZURE_SEARCH_URL_COLUMN = "metadata"
AZURE_SEARCH_FILTER = "filter"
AZURE_SEARCH_ENABLE_IN_DOMAIN = "true"
AZURE_SEARCH_TOP_K = 5
AZURE_SEARCH_USE_SEMANTIC_SEARCH = "true"
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "test-config"
AZURE_OPENAI_TEMPERATURE = "0.5"
AZURE_OPENAI_MAX_TOKENS = "500"
AZURE_OPENAI_TOP_P = "0.8"
AZURE_OPENAI_STOP_SEQUENCE = "\n|STOP"
AZURE_SPEECH_RECOGNIZER_LANGUAGES = ["en-US", "en-GB"]


@pytest.fixture
def client():
    """Create a test client for the app."""
    return create_app().test_client()


@pytest.fixture(autouse=True)
def env_helper_mock():
    """Mock the environment variables for the tests."""
    with patch("create_app.EnvHelper") as mock:
        env_helper = mock.return_value

        env_helper.AZURE_SPEECH_KEY = AZURE_SPEECH_KEY
        env_helper.AZURE_SPEECH_SERVICE_REGION = AZURE_SPEECH_SERVICE_REGION
        env_helper.AZURE_SPEECH_RECOGNIZER_LANGUAGES = AZURE_SPEECH_RECOGNIZER_LANGUAGES
        env_helper.AZURE_SPEECH_REGION_ENDPOINT = AZURE_SPEECH_REGION_ENDPOINT
        env_helper.AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT
        env_helper.AZURE_OPENAI_MODEL = AZURE_OPENAI_MODEL
        env_helper.AZURE_OPENAI_EMBEDDING_MODEL = AZURE_OPENAI_EMBEDDING_MODEL
        env_helper.AZURE_OPENAI_SYSTEM_MESSAGE = AZURE_OPENAI_SYSTEM_MESSAGE
        env_helper.AZURE_OPENAI_API_VERSION = AZURE_OPENAI_API_VERSION
        env_helper.AZURE_OPENAI_API_KEY = AZURE_OPENAI_API_KEY
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_OPENAI_TEMPERATURE = AZURE_OPENAI_TEMPERATURE
        env_helper.AZURE_OPENAI_MAX_TOKENS = AZURE_OPENAI_MAX_TOKENS
        env_helper.AZURE_OPENAI_TOP_P = AZURE_OPENAI_TOP_P
        env_helper.AZURE_OPENAI_STOP_SEQUENCE = AZURE_OPENAI_STOP_SEQUENCE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_CONTENT_COLUMN = AZURE_SEARCH_CONTENT_COLUMN
        env_helper.AZURE_SEARCH_CONTENT_VECTOR_COLUMN = (
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN
        )
        env_helper.AZURE_SEARCH_TITLE_COLUMN = AZURE_SEARCH_TITLE_COLUMN
        env_helper.AZURE_SEARCH_SOURCE_COLUMN = AZURE_SEARCH_SOURCE_COLUMN
        env_helper.AZURE_SEARCH_TEXT_COLUMN = AZURE_SEARCH_TEXT_COLUMN
        env_helper.AZURE_SEARCH_LAYOUT_TEXT_COLUMN = AZURE_SEARCH_LAYOUT_TEXT_COLUMN
        env_helper.AZURE_SEARCH_FILENAME_COLUMN = AZURE_SEARCH_FILENAME_COLUMN
        env_helper.AZURE_SEARCH_URL_COLUMN = AZURE_SEARCH_URL_COLUMN
        env_helper.AZURE_SEARCH_FILTER = AZURE_SEARCH_FILTER
        env_helper.AZURE_SEARCH_ENABLE_IN_DOMAIN = AZURE_SEARCH_ENABLE_IN_DOMAIN
        env_helper.AZURE_SEARCH_TOP_K = AZURE_SEARCH_TOP_K
        env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH = AZURE_SEARCH_USE_SEMANTIC_SEARCH
        env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = (
            AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
        )
        env_helper.SHOULD_STREAM = True
        env_helper.is_auth_type_keys.return_value = True
        env_helper.CONVERSATION_FLOW = ConversationFlow.CUSTOM.value

        yield env_helper


class TestSpeechToken:
    @patch("create_app.requests")
    def test_returns_speech_token_using_keys(
        self, requests: MagicMock, client: FlaskClient
    ):
        """Test that the speech token is returned correctly when using keys."""
        # given
        mock_response: MagicMock = requests.post.return_value
        mock_response.text = "speech-token"
        mock_response.status_code = 200

        # when
        response = client.get("/api/speech")

        # then
        assert response.status_code == 200
        assert response.json == {
            "token": "speech-token",
            "region": AZURE_SPEECH_SERVICE_REGION,
            "languages": AZURE_SPEECH_RECOGNIZER_LANGUAGES,
            "key": "mock-speech-key",
        }

        requests.post.assert_called_once_with(
            f"{AZURE_SPEECH_REGION_ENDPOINT}sts/v1.0/issueToken",
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            },
            timeout=5,
        )

    @patch("create_app.CognitiveServicesManagementClient")
    @patch("create_app.requests")
    def test_returns_speech_token_using_rbac(
        self,
        requests: MagicMock,
        CognitiveServicesManagementClientMock: MagicMock,
        env_helper_mock: MagicMock,
        client: FlaskClient,
    ):
        """Test that the speech token is returned correctly when using RBAC."""
        # given
        env_helper_mock.AZURE_SPEECH_KEY = None

        mock_cognitive_services_client_mock = (
            CognitiveServicesManagementClientMock.return_value
        )
        mock_cognitive_services_client_mock.accounts.list_keys.return_value = MagicMock(
            key1="mock-key1", key2="mock-key2"
        )

        mock_response: MagicMock = requests.post.return_value
        mock_response.text = "speech-token"
        mock_response.status_code = 200

        # when
        response = client.get("/api/speech")

        # then
        assert response.status_code == 200
        assert response.json == {
            "token": "speech-token",
            "region": AZURE_SPEECH_SERVICE_REGION,
            "languages": AZURE_SPEECH_RECOGNIZER_LANGUAGES,
            "key": "mock-key1",
        }

        requests.post.assert_called_once_with(
            f"{AZURE_SPEECH_REGION_ENDPOINT}sts/v1.0/issueToken",
            headers={
                "Ocp-Apim-Subscription-Key": "mock-key1",
            },
            timeout=5,
        )

    @patch("create_app.requests")
    def test_error_when_cannot_retrieve_speech_token(
        self, requests: MagicMock, client: FlaskClient
    ):
        """Test that an error is returned when the speech token cannot be retrieved."""
        # given
        mock_response: MagicMock = requests.post.return_value
        mock_response.text = "error"
        mock_response.status_code = 400

        # when
        response = client.get("/api/speech")

        # then
        assert response.status_code == 400
        assert response.json == {"error": "Failed to get speech config"}

    @patch("create_app.requests")
    def test_error_when_unexpected_error_occurs(
        self, requests: MagicMock, client: FlaskClient
    ):
        """Test that an error is returned when an unexpected error occurs."""
        # given
        requests.post.side_effect = Exception("An error occurred")

        # when
        response = client.get("/api/speech")

        assert response.status_code == 500
        assert response.json == {"error": "Failed to get speech config"}


class TestConfig:
    """Test the config endpoint."""

    def test_health(self, client):
        """Test that the health endpoint returns OK."""
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.text == "OK"


class TestConversationCustom:
    """Test the custom conversation endpoint."""

    def setup_method(self):
        """Set up the test data."""
        self.orchestrator_config = {"strategy": "langchain"}
        self.messages = [
            {
                "content": '{"citations": [], "intent": "A question?"}',
                "end_turn": False,
                "role": "tool",
            },
            {"content": "An answer", "end_turn": True, "role": "assistant"},
        ]
        self.openai_model = "mock-model"
        self.body = {
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
            ],
        }

    @patch("create_app.get_message_orchestrator")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_custom_returns_correct_response(
        self,
        get_active_config_or_default_mock,
        get_message_orchestrator_mock,
        env_helper_mock,
        client,
    ):
        """Test that the custom conversation endpoint returns the correct response."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        get_active_config_or_default_mock.return_value.orchestrator.return_value = (
            self.orchestrator_config
        )

        message_orchestrator_mock = AsyncMock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        env_helper_mock.AZURE_OPENAI_MODEL = self.openai_model

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "choices": [{"messages": self.messages}],
            "created": "response.created",
            "id": "response.id",
            "model": self.openai_model,
            "object": "response.object",
        }

    @patch("create_app.get_message_orchestrator")
    @patch("create_app.get_orchestrator_config")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_custom_calls_message_orchestrator_correctly(
        self,
        get_active_config_or_default_mock,
        get_orchestrator_config_mock,
        get_message_orchestrator_mock,
        env_helper_mock,
        client,
    ):
        """Test that the custom conversation endpoint calls the message orchestrator correctly."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = AsyncMock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        env_helper_mock.AZURE_OPENAI_MODEL = self.openai_model

        # when
        client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        message_orchestrator_mock.handle_message.assert_called_once_with(
            user_message=self.body["messages"][-1]["content"],
            chat_history=self.body["messages"][:-1],
            conversation_id=self.body["conversation_id"],
            orchestrator=self.orchestrator_config,
        )

    @patch("create_app.get_orchestrator_config")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversaation_custom_returns_error_response_on_exception(
        self, get_active_config_or_default_mock, get_orchestrator_config_mock, client
    ):
        """Test that an error response is returned when an exception occurs."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        get_orchestrator_config_mock.side_effect = Exception("An error occurred")

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "An error occurred. Please try again. If the problem persists, please contact the site administrator."
        }

    @patch("create_app.get_orchestrator_config")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_custom_returns_error_response_on_rate_limit_error(
        self, get_active_config_or_default_mock, get_orchestrator_config_mock, client
    ):
        """Test that a 429 response is returned on RateLimitError."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        response_mock = Mock()
        response_mock.status_code = 429
        response_mock.json.return_value = {
            "error": {
                "code": "429",
                "message": "Requests to the Embeddings_Create Operation under Azure OpenAI API version 2024-02-01 "
                "have exceeded call rate limit of your current OpenAI S0 pricing tier. Please retry after "
                "2 seconds. Please go here: https://aka.ms/oai/quotaincrease if you would like to further "
                "increase the default rate limit.",
            }
        }
        body_mock = {"error": "Rate limit exceeded"}

        rate_limit_error = RateLimitError(
            "Rate limit exceeded", response=response_mock, body=body_mock
        )
        get_orchestrator_config_mock.side_effect = rate_limit_error

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 429
        assert response.json == {
            "error": "We're currently experiencing a high number of requests for the service you're trying to access. "
            "Please wait a moment and try again."
        }

    @patch("create_app.get_orchestrator_config")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_custom_returns_500_when_internalservererror_occurs(
        self, get_active_config_or_default_mock, get_orchestrator_config_mock, client
    ):
        """Test that an error response is returned when an exception occurs."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        response_mock = MagicMock()
        response_mock.status_code = 500
        get_orchestrator_config_mock.side_effect = InternalServerError(
            "Test exception", response=response_mock, body=""
        )

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "An error occurred. Please try again. If the problem persists, please contact the site "
            "administrator."
        }

    @patch("create_app.get_message_orchestrator")
    @patch("create_app.get_orchestrator_config")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_custom_allows_multiple_messages_from_user(
        self,
        get_active_config_or_default_mock,
        get_orchestrator_config_mock,
        get_message_orchestrator_mock,
        client,
    ):
        """This can happen if there was an error getting a response from the assistant for the previous user message."""

        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "custom"
        )
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = AsyncMock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        body = {
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
                {
                    "role": "user",
                    "content": "Please, what is the meaning of life?",
                },
            ],
        }

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=body,
        )

        # then
        assert response.status_code == 200
        message_orchestrator_mock.handle_message.assert_called_once_with(
            user_message=body["messages"][-1]["content"],
            chat_history=body["messages"][:-1],
            conversation_id=body["conversation_id"],
            orchestrator=self.orchestrator_config,
        )

    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_returns_error_response_on_incorrect_conversation_flow_input(
        self,
        get_active_config_or_default_mock,
        client,
    ):
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "bob"
        )

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "Invalid conversation flow configured. Value can only be 'custom' or 'byod'."
        }


class TestConversationAzureByod:
    def setup_method(self):
        """Set up the test data."""
        self.body = {
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
            ],
        }

        self.content = "mock content"

        self.mock_response = MagicMock(
            id="response.id",
            model="mock-model",
            created=0,
            object="response.object",
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=self.content,
                        model_extra={
                            "context": {
                                "citations": [
                                    {
                                        "content": "content",
                                        "title": "title",
                                        "url": '{"id": "doc_id", "source": "source", "title": "title", "chunk": 46, "chunk_id": null}',
                                    }
                                ],
                                "intent": "intent",
                            }
                        },
                    )
                )
            ],
        )

        self.mock_streamed_response = [
            MagicMock(
                id="response.id",
                model=AZURE_OPENAI_MODEL,
                created=0,
                object="response.object",
                choices=[
                    MagicMock(
                        delta=MagicMock(
                            role="assistant",
                            model_extra={
                                "context": {
                                    "citations": [
                                        {
                                            "content": "content",
                                            "title": "title",
                                            "url": '{"id": "doc_id", "source": "source", "title": "title", "chunk": 46, "chunk_id": null}',
                                        }
                                    ],
                                    "intent": "intent",
                                }
                            },
                        ),
                        model_extra={
                            "end_turn": False,
                        },
                    )
                ],
            ),
            MagicMock(
                id="response.id",
                model=AZURE_OPENAI_MODEL,
                created=0,
                object="response.object",
                choices=[
                    MagicMock(
                        delta=MagicMock(
                            content="A question\n?",
                        ),
                        model_extra={
                            "end_turn": False,
                        },
                    )
                ],
            ),
            MagicMock(
                id="response.id",
                model=AZURE_OPENAI_MODEL,
                created=0,
                object="response.object",
                choices=[
                    MagicMock(
                        model_extra={
                            "end_turn": True,
                        }
                    )
                ],
            ),
        ]

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas"
    )
    def test_conversation_azure_byod_returns_correct_response_when_streaming_with_data_keys(
        self,
        generate_container_sas_mock: MagicMock,
        get_active_config_or_default_mock,
        azure_openai_mock: MagicMock,
        index_not_exists_mock,
        env_helper_mock: MagicMock,
        client: FlaskClient,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create.return_value = (
            self.mock_streamed_response
        )

        get_active_config_or_default_mock.return_value.prompts.use_on_your_data_format = (
            False
        )
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        generate_container_sas_mock.return_value = "mock-sas"
        index_not_exists_mock.return_value = False

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        # The response is JSON lines
        data = str(response.data, "utf-8")
        assert (
            data
            == r"""{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": true, "role": "assistant"}]}]}
"""
        )

        azure_openai_mock.assert_called_once_with(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            api_key=AZURE_OPENAI_API_KEY,
        )

        openai_client_mock.chat.completions.create.assert_called_once_with(
            model=AZURE_OPENAI_MODEL,
            messages=self.body["messages"],
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            stop=["\n", "STOP"],
            stream=True,
            extra_body={
                "data_sources": [
                    {
                        "type": "azure_search",
                        "parameters": {
                            "authentication": {
                                "type": "api_key",
                                "key": AZURE_SEARCH_KEY,
                            },
                            "endpoint": AZURE_SEARCH_SERVICE,
                            "index_name": AZURE_SEARCH_INDEX,
                            "fields_mapping": {
                                "content_fields": ["field1", "field2"],
                                "vector_fields": [AZURE_SEARCH_CONTENT_VECTOR_COLUMN],
                                "title_field": AZURE_SEARCH_TITLE_COLUMN,
                                "url_field": env_helper_mock.AZURE_SEARCH_FIELDS_METADATA,
                                "filepath_field": AZURE_SEARCH_FILENAME_COLUMN,
                                "source_field": AZURE_SEARCH_SOURCE_COLUMN,
                                "text_field": AZURE_SEARCH_TEXT_COLUMN,
                                "layoutText_field": AZURE_SEARCH_LAYOUT_TEXT_COLUMN,
                            },
                            "filter": AZURE_SEARCH_FILTER,
                            "in_scope": AZURE_SEARCH_ENABLE_IN_DOMAIN,
                            "top_n_documents": AZURE_SEARCH_TOP_K,
                            "embedding_dependency": {
                                "type": "deployment_name",
                                "deployment_name": AZURE_OPENAI_EMBEDDING_MODEL,
                            },
                            "query_type": "vector_semantic_hybrid",
                            "semantic_configuration": AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
                            "role_information": AZURE_OPENAI_SYSTEM_MESSAGE,
                        },
                    }
                ]
            },
        )

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas"
    )
    def test_conversation_azure_byod_returns_correct_response_when_streaming_with_data_rbac(
        self,
        generate_container_sas_mock: MagicMock,
        get_active_config_or_default_mock,
        azure_openai_mock: MagicMock,
        index_not_exists_mock,
        env_helper_mock: MagicMock,
        client: FlaskClient,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        env_helper_mock.is_auth_type_keys.return_value = False
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        generate_container_sas_mock.return_value = "mock-sas"
        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create.return_value = (
            self.mock_streamed_response
        )
        index_not_exists_mock.return_value = False

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        # The response is JSON lines
        data = str(response.data, "utf-8")
        assert (
            data
            == r"""{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"[title](source)\\n\\n\\ncontent\", \"id\": \"doc_id\", \"chunk_id\": 46, \"title\": \"title\", \"filepath\": \"title\", \"url\": \"[title](source)\"}]}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": true, "role": "assistant"}]}]}
"""
        )

        azure_openai_mock.assert_called_once_with(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_ad_token_provider=ANY,
        )

        kwargs = openai_client_mock.chat.completions.create.call_args.kwargs

        assert kwargs["extra_body"]["data_sources"][0]["parameters"][
            "authentication"
        ] == {
            "type": "system_assigned_managed_identity",
        }

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas"
    )
    def test_conversation_azure_byod_returns_correct_response_when_not_streaming_with_data(
        self,
        generate_container_sas_mock: MagicMock,
        get_active_config_or_default_mock,
        azure_openai_mock: MagicMock,
        index_not_exists_mock,
        env_helper_mock: MagicMock,
        client: FlaskClient,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        env_helper_mock.SHOULD_STREAM = False
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        generate_container_sas_mock.return_value = "mock-sas"
        index_not_exists_mock.return_value = False
        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create.return_value = self.mock_response

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": "mock-model",
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "messages": [
                        {
                            "content": '{"citations": [{"content": "[title](source)\\n\\n\\ncontent", "id": "doc_id", "chunk_id": 46, "title": "title", "filepath": "title", "url": "[title](source)"}]}',
                            "end_turn": False,
                            "role": "tool",
                        },
                        {
                            "content": self.content,
                            "end_turn": True,
                            "role": "assistant",
                        },
                    ]
                }
            ],
        }

    @patch("create_app.conversation_with_data")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_500_when_exception_occurs(
        self,
        get_active_config_or_default_mock,
        conversation_with_data_mock,
        client,
    ):
        """Test that an error response is returned when an exception occurs."""
        # given
        conversation_with_data_mock.side_effect = Exception("Test exception")
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "An error occurred. Please try again. If the problem persists, please contact the site administrator."
        }

    @patch("create_app.conversation_with_data")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_500_when_internalservererror_occurs(
        self,
        get_active_config_or_default_mock,
        conversation_with_data_mock,
        client,
    ):
        """Test that an error response is returned when an exception occurs."""
        # given
        response_mock = MagicMock()
        response_mock.status_code = 500
        conversation_with_data_mock.side_effect = InternalServerError(
            "Test exception", response=response_mock, body=""
        )
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "An error occurred. Please try again. If the problem persists, please contact the site "
            "administrator."
        }

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.conversation_with_data")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_429_on_rate_limit_error(
        self,
        get_active_config_or_default_mock,
        conversation_with_data_mock,
        index_not_exists_mock,
        client,
    ):
        """Test that a 429 response is returned on RateLimitError for BYOD conversation."""
        # given
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.json.return_value = {
            "error": {
                "requestid": "f30740e1-c6e1-48ab-ab1e-35469ed41ba4",
                "code": "400",
                "message": "An error occurred when calling Azure OpenAI: Rate limit reached for AOAI embedding "
                'resource: Server responded with status 429. Error message: {"error":{"code":"429",'
                '"message": "Rate limit is exceeded. Try again in 44 seconds."}}',
            }
        }

        conversation_with_data_mock.side_effect = BadRequestError(
            message="Error code: 400", response=response_mock, body=""
        )
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        index_not_exists_mock.return_value = False

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 429
        assert response.json == {
            "error": "We're currently experiencing a high number of requests for the service you're trying to access. "
            "Please wait a moment and try again."
        }

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_correct_response_when_not_streaming_without_data_keys(
        self,
        get_active_config_or_default_mock,
        azure_openai_mock,
        index_not_exists_mock,
        env_helper_mock,
        client,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        env_helper_mock.SHOULD_STREAM = False
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        index_not_exists_mock.return_value = True
        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        openai_create_mock = MagicMock(
            id="response.id",
            model=AZURE_OPENAI_MODEL,
            created=0,
            object="response.object",
        )
        openai_create_mock.choices[0].message.content = self.content
        openai_client_mock.chat.completions.create.return_value = openai_create_mock

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": AZURE_OPENAI_MODEL,
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": self.content,
                        }
                    ]
                }
            ],
        }

        azure_openai_mock.assert_called_once_with(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            api_key=AZURE_OPENAI_API_KEY,
        )

        openai_client_mock.chat.completions.create.assert_called_once_with(
            model=AZURE_OPENAI_MODEL,
            messages=[{"role": "system", "content": "system-message"}]
            + self.body["messages"],
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            stop=["\n", "STOP"],
            stream=False,
        )

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_correct_response_when_not_streaming_without_data_rbac(
        self,
        get_active_config_or_default_mock,
        azure_openai_mock,
        index_not_exists_mock,
        env_helper_mock,
        client,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        env_helper_mock.SHOULD_STREAM = False
        env_helper_mock.AZURE_AUTH_TYPE = "rbac"
        env_helper_mock.AZURE_OPENAI_STOP_SEQUENCE = ""
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        index_not_exists_mock.return_value = True

        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        openai_create_mock = MagicMock(
            id="response.id",
            model=AZURE_OPENAI_MODEL,
            created=0,
            object="response.object",
        )
        openai_create_mock.choices[0].message.content = self.content
        openai_client_mock.chat.completions.create.return_value = openai_create_mock

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": AZURE_OPENAI_MODEL,
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": self.content,
                        }
                    ]
                }
            ],
        }

        azure_openai_mock.assert_called_once_with(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_ad_token_provider=env_helper_mock.AZURE_TOKEN_PROVIDER,
        )

        openai_client_mock.chat.completions.create.assert_called_once_with(
            model=AZURE_OPENAI_MODEL,
            messages=[{"role": "system", "content": "system-message"}]
            + self.body["messages"],
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            stop=None,
            stream=False,
        )

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    def test_conversation_azure_byod_returns_correct_response_when_streaming_without_data(
        self,
        get_active_config_or_default_mock,
        azure_openai_mock,
        index_not_exists_mock,
        env_helper_mock,
        client,
    ):
        """Test that the Azure BYOD conversation endpoint returns the correct response."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        index_not_exists_mock.return_value = True
        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        mock_response = MagicMock(
            id="response.id",
            model=AZURE_OPENAI_MODEL,
            created=0,
            object="response.object",
        )
        mock_response.choices[0].delta.content = self.content

        openai_client_mock.chat.completions.create.return_value = [mock_response]

        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        data = str(response.data, "utf-8")
        assert (
            data
            == '{"id": "response.id", "model": "mock-openai-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"role": "assistant", "content": "mock content"}]}]}\n'
        )

    @patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper._index_not_exists"
    )
    @patch("create_app.AzureOpenAI")
    @patch(
        "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
    )
    @patch(
        "backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas"
    )
    def test_conversation_azure_byod_uses_semantic_config(
        self,
        generate_container_sas_mock: MagicMock,
        get_active_config_or_default_mock,
        azure_openai_mock: MagicMock,
        index_not_exists_mock,
        client: FlaskClient,
    ):
        """Test that the Azure BYOD conversation endpoint uses the semantic configuration."""
        # given
        get_active_config_or_default_mock.return_value.prompts.conversational_flow = (
            "byod"
        )
        generate_container_sas_mock.return_value = "mock-sas"
        openai_client_mock = azure_openai_mock.return_value
        openai_client_mock.chat.completions.create.return_value = (
            self.mock_streamed_response
        )
        index_not_exists_mock.return_value = False
        # when
        response = client.post(
            "/api/conversation",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        kwargs = openai_client_mock.chat.completions.create.call_args.kwargs

        assert (
            kwargs["extra_body"]["data_sources"][0]["parameters"]["query_type"]
            == "vector_semantic_hybrid"
        )
        assert (
            kwargs["extra_body"]["data_sources"][0]["parameters"][
                "semantic_configuration"
            ]
            == "test-config"
        )
