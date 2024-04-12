import json
import os
import pytest
from unittest.mock import MagicMock, Mock, patch
from create_app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def env_helper_mock(autouse=True):
    patcher = patch("create_app.EnvHelper")

    EnvHelperMock = patcher.start()
    mock = EnvHelperMock.return_value
    yield mock

    patcher.stop()


class TestConfig:
    def test_returns_correct_config(self, client):
        response = client.get("/api/config")

        assert response.status_code == 200
        assert response.json == {
            "azureSpeechKey": "",
            "azureSpeechRegion": None,
            "AZURE_OPENAI_ENDPOINT": "https://.openai.azure.com/",
        }


class TestConversationCustom:
    def setup_method(self):
        self.orchestrator_config = {"strategy": "langchain"}
        self.messages = [
            {
                "content": '{"citations": [], "intent": "A question?"}',
                "end_turn": False,
                "role": "tool",
            },
            {"content": "An answer", "end_turn": True, "role": "assistant"},
        ]
        self.openai_model = "some-model"
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
        "backend.batch.utilities.helpers.ConfigHelper.ConfigHelper.get_active_config_or_default"
    )
    def test_converstation_custom_returns_correct_response(
        self,
        get_active_config_or_default_mock,
        get_message_orchestrator_mock,
        env_helper_mock,
        client,
    ):
        # given
        get_active_config_or_default_mock.return_value.orchestrator.return_value = (
            self.orchestrator_config
        )

        message_orchestrator_mock = Mock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        env_helper_mock.AZURE_OPENAI_MODEL = self.openai_model

        # when
        response = client.post(
            "/api/conversation/custom",
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
    def test_converstation_custom_calls_message_orchestrator_correctly(
        self,
        get_orchestrator_config_mock,
        get_message_orchestrator_mock,
        client,
    ):
        # given
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = Mock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        os.environ["AZURE_OPENAI_MODEL"] = self.openai_model

        # when
        client.post(
            "/api/conversation/custom",
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
    def test_converstation_custom_returns_error_resonse_on_exception(
        self, get_orchestrator_config_mock, client
    ):
        # given
        get_orchestrator_config_mock.side_effect = Exception("An error occurred")

        # when
        response = client.post(
            "/api/conversation/custom",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "Exception in /api/conversation/custom. See log for more details."
        }

    @patch("create_app.get_message_orchestrator")
    @patch("create_app.get_orchestrator_config")
    def test_converstation_custom_allows_multiple_messages_from_user(
        self, get_orchestrator_config_mock, get_message_orchestrator_mock, client
    ):
        """This can happen if there was an error getting a response from the assistant for the previous user message."""

        # given
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = Mock()
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
            "/api/conversation/custom",
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


class MockResponse:

    def __init__(self, include_error=False):
        self.include_error = include_error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return True

    # Return a mock streamed response
    def iter_lines(self, chunk_size=512):
        assistant = {
            "id": "response.id",
            "model": "some-model",
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "context": {
                            "citations": [
                                {
                                    "content": "content",
                                    "title": "title",
                                }
                            ],
                            "intent": "intent",
                        },
                    },
                    "end_turn": False,
                    "finish_reason": None,
                }
            ],
        }

        message = {
            "id": "response.id",
            "model": "some-model",
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "delta": {"content": "A question\n?"},
                    "end_turn": False,
                    "finish_reason": None,
                }
            ],
        }

        end = {
            "id": "response.id",
            "model": "some-model",
            "created": 0,
            "object": "response.object",
            "choices": [{"delta": {}, "end_turn": True, "finish_reason": "stop"}],
        }

        if self.include_error:
            assistant["error"] = "An error occurred\n"

        response = [
            bytes(f"data: {json.dumps(res)}", "utf-8")
            for res in (assistant, message, end)
        ]

        # The streamed response has empty lines between each response, and a final message of "[DONE]"
        response.insert(1, b"")
        response.insert(3, b"")
        response += [b"data: [DONE]"]

        return response


class TestConversationAzureByod:
    def setup_method(self):
        self.body = {
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
            ],
        }

        self.system_message = "system-message"
        self.openai_model = "some-model"
        self.openai_endpoint = "some-endpoint"
        self.content = "some content"
        self.openai_api_version = "some-version"
        self.openai_api_key = "some-api-key"
        self.search_key = "some-search-key"
        self.token = "some-token"
        self.temperature = "0.5"
        self.max_tokens = "500"
        self.top_p = "0.8"
        self.stop_sequence = "\n|STOP"

    @pytest.fixture(autouse=True)
    def setup_env_helper_mock(self, env_helper_mock):
        # These are the default values for the env_helper
        # They can be overridden within each test
        env_helper_mock.AZURE_OPENAI_SYSTEM_MESSAGE = self.system_message
        env_helper_mock.AZURE_OPENAI_MODEL = self.openai_model
        env_helper_mock.AZURE_OPENAI_ENDPOINT = self.openai_endpoint
        env_helper_mock.AZURE_OPENAI_API_VERSION = self.openai_api_version
        env_helper_mock.AZURE_OPENAI_API_KEY = self.openai_api_key
        env_helper_mock.AZURE_SEARCH_KEY = self.search_key
        env_helper_mock.AZURE_TOKEN_PROVIDER.return_value = self.token
        env_helper_mock.AZURE_OPENAI_TEMPERATURE = self.temperature
        env_helper_mock.AZURE_OPENAI_MAX_TOKENS = self.max_tokens
        env_helper_mock.AZURE_OPENAI_TOP_P = self.top_p
        env_helper_mock.AZURE_OPENAI_STOP_SEQUENCE = self.stop_sequence
        env_helper_mock.SHOULD_STREAM = True
        env_helper_mock.AZURE_AUTH_TYPE = "keys"
        env_helper_mock.should_use_data.return_value = True

    @patch("create_app.requests.Session")
    def test_converstation_azure_byod_returns_correct_response_when_streaming_with_data_keys(
        self, get_requests_session_mock, client
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse()
        mock_session.post = Mock(return_value=response_mock)

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        # The response is JSON lines
        data = str(response.data, "utf-8")
        assert (
            data
            == r"""{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": true, "role": "assistant"}]}]}
"""
        )

        request_body = mock_session.post.call_args[1]["json"]
        request_headers = mock_session.post.call_args[1]["headers"]

        assert request_body["data_sources"][0]["parameters"]["authentication"] == {
            "type": "api_key",
            "key": self.search_key,
        }
        assert request_headers["api-key"] == self.openai_api_key

    @patch("create_app.requests.Session")
    def test_converstation_azure_byod_returns_correct_response_when_streaming_with_data_rbac(
        self, get_requests_session_mock, env_helper_mock, client
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse()
        mock_session.post = Mock(return_value=response_mock)
        env_helper_mock.AZURE_AUTH_TYPE = "rbac"

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        # The response is JSON lines
        data = str(response.data, "utf-8")
        assert (
            data
            == r"""{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\"citations\": [{\"content\": \"content\", \"title\": \"title\"}], \"intent\": \"intent\"}", "end_turn": false, "role": "tool"}, {"content": "A question\n?", "end_turn": true, "role": "assistant"}]}]}
"""
        )

        request_body = mock_session.post.call_args[1]["json"]
        request_headers = mock_session.post.call_args[1]["headers"]

        assert request_body["data_sources"][0]["parameters"]["authentication"] == {
            "type": "system_assigned_managed_identity"
        }
        assert request_headers["Authorization"] == f"Bearer {self.token}"

    @patch("create_app.requests.post")
    def test_converstation_azure_byod_returns_correct_response_when_not_streaming_with_data(
        self, post_mock, env_helper_mock, client
    ):
        # given
        env_helper_mock.SHOULD_STREAM = False

        post_mock.return_value.status_code = 200
        post_mock.return_value.json.return_value = {
            "id": "response.id",
            "model": "some-model",
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "message": {
                        "content": self.content,
                        "context": {"context": "some-context"},
                    }
                }
            ],
        }

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": "some-model",
            "created": 0,
            "object": "response.object",
            "choices": [
                {
                    "messages": [
                        {
                            "content": '{"context": "some-context"}',
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

    @patch("create_app.requests.Session")
    def test_converstation_azure_byod_receives_error_from_search_when_streaming_with_data(
        self, get_requests_session_mock, client
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse(include_error=True)
        mock_session.post = Mock(return_value=response_mock)

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert b'"error": "An error occurred\\n"' in response.data

    @patch("create_app.requests.Session")
    def test_converstation_azure_byod_throws_exception_when_streaming_with_data(
        self, get_requests_session_mock, client
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        mock_session.post.side_effect = ValueError("Test exception")

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert b'{"error": "Test exception"}\n' in response.data

    @patch("create_app.conversation_with_data")
    def test_converstation_azure_byod_returns_500_when_exception_occurs(
        self, conversation_with_data_mock, client
    ):
        # given
        conversation_with_data_mock.side_effect = Exception("Test exception")

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "Exception in /api/conversation/azure_byod. See log for more details."
        }

    @patch("create_app.AzureOpenAI")
    def test_converstation_azure_byod_returns_correct_response_when_not_streaming_without_data_keys(
        self, azure_openai_mock, env_helper_mock, client
    ):
        # given
        env_helper_mock.should_use_data.return_value = False
        env_helper_mock.SHOULD_STREAM = False

        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        openai_create_mock = MagicMock(
            id="response.id",
            model="some-model",
            created=0,
            object="response.object",
        )
        openai_create_mock.choices[0].message.content = self.content
        openai_client_mock.chat.completions.create.return_value = openai_create_mock

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": "some-model",
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
            azure_endpoint=self.openai_endpoint,
            api_version=self.openai_api_version,
            api_key=self.openai_api_key,
        )

        openai_client_mock.chat.completions.create.assert_called_once_with(
            model="some-model",
            messages=[{"role": "system", "content": "system-message"}]
            + self.body["messages"],
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            stop=["\n", "STOP"],
            stream=False,
        )

    @patch("create_app.AzureOpenAI")
    def test_converstation_azure_byod_returns_correct_response_when_not_streaming_without_data_rbac(
        self, azure_openai_mock, env_helper_mock, client
    ):
        # given
        env_helper_mock.should_use_data.return_value = False
        env_helper_mock.SHOULD_STREAM = False
        env_helper_mock.AZURE_AUTH_TYPE = "rbac"
        env_helper_mock.AZURE_OPENAI_STOP_SEQUENCE = ""

        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        openai_create_mock = MagicMock(
            id="response.id",
            model="some-model",
            created=0,
            object="response.object",
        )
        openai_create_mock.choices[0].message.content = self.content
        openai_client_mock.chat.completions.create.return_value = openai_create_mock

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert response.json == {
            "id": "response.id",
            "model": "some-model",
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
            azure_endpoint=self.openai_endpoint,
            api_version=self.openai_api_version,
            azure_ad_token_provider=env_helper_mock.AZURE_TOKEN_PROVIDER,
        )

        openai_client_mock.chat.completions.create.assert_called_once_with(
            model="some-model",
            messages=[{"role": "system", "content": "system-message"}]
            + self.body["messages"],
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            stop=None,
            stream=False,
        )

    @patch("create_app.AzureOpenAI")
    def test_converstation_azure_byod_returns_correct_response_when_streaming_without_data(
        self, azure_openai_mock, env_helper_mock, client
    ):
        # given
        env_helper_mock.should_use_data.return_value = False

        openai_client_mock = MagicMock()
        azure_openai_mock.return_value = openai_client_mock

        mock_response = MagicMock(
            id="response.id",
            model="some-model",
            created=0,
            object="response.object",
        )
        mock_response.choices[0].delta.content = self.content

        openai_client_mock.chat.completions.create.return_value = [mock_response]

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        data = str(response.data, "utf-8")
        assert (
            data
            == '{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"role": "assistant", "content": "some content"}]}]}\n'
        )

    @patch("create_app.requests.Session")
    def test_converstation_azure_byod_uses_semantic_config(
        self, get_requests_session_mock, env_helper_mock, client
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse()
        mock_session.post = Mock(return_value=response_mock)
        env_helper_mock.SHOULD_STREAM = True
        env_helper_mock.AZURE_SEARCH_USE_SEMANTIC_SEARCH = True
        env_helper_mock.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "test-config"

        # when
        response = client.post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200

        request_body = mock_session.post.call_args[1]["json"]

        assert request_body["data_sources"][0]["parameters"]["query_type"] == "semantic"
        assert (
            request_body["data_sources"][0]["parameters"]["semantic_configuration"]
            == "test-config"
        )
