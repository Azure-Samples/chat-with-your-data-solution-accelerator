import json
import os

from unittest.mock import Mock
from unittest.mock import patch

from app import app


class TestConfig:
    def test_returns_correct_config(self):
        response = app.test_client().get("/api/config")

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

    @patch("app.get_message_orchestrator")
    @patch("app.get_orchestrator_config")
    @patch("app.env_helper")
    def test_converstation_custom_returns_correct_response(
        self,
        env_helper_mock,
        get_orchestrator_config_mock,
        get_message_orchestrator_mock,
    ):
        # given
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = Mock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        env_helper_mock.AZURE_OPENAI_MODEL = self.openai_model

        # when
        response = app.test_client().post(
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

    @patch("app.get_message_orchestrator")
    @patch("app.get_orchestrator_config")
    def test_converstation_custom_calls_message_orchestrator_correctly(
        self, get_orchestrator_config_mock, get_message_orchestrator_mock
    ):
        # given
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = Mock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        os.environ["AZURE_OPENAI_MODEL"] = self.openai_model

        # when
        app.test_client().post(
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

    @patch("app.get_orchestrator_config")
    def test_converstation_custom_returns_error_resonse_on_exception(
        self, get_orchestrator_config_mock
    ):
        # given
        get_orchestrator_config_mock.side_effect = Exception("An error occurred")

        # when
        response = app.test_client().post(
            "/api/conversation/custom",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 500
        assert response.json == {
            "error": "Exception in /api/conversation/custom. See log for more details."
        }

    @patch("app.get_message_orchestrator")
    @patch("app.get_orchestrator_config")
    def test_converstation_custom_allows_multiple_messages_from_user(
        self, get_orchestrator_config_mock, get_message_orchestrator_mock
    ):
        """This can happen if there was an error getting a response from the assistant for the previous user message."""

        # given
        get_orchestrator_config_mock.return_value = self.orchestrator_config

        message_orchestrator_mock = Mock()
        message_orchestrator_mock.handle_message.return_value = self.messages
        get_message_orchestrator_mock.return_value = message_orchestrator_mock

        os.environ["AZURE_OPENAI_MODEL"] = self.openai_model

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
        response = app.test_client().post(
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

    @patch("app.requests.Session")
    @patch("app.env_helper")
    def test_converstation_azure_byod_returns_correct_response_when_streaming_with_data(
        self, env_helper_mock, get_requests_session_mock
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse()
        mock_session.post = Mock(return_value=response_mock)
        env_helper_mock.should_use_data.return_value = True

        # when
        response = app.test_client().post(
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
            == """{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\\"citations\\": [{\\"content\\": \\"content\\", \\"title\\": \\"title\\"}], \\"intent\\": \\"intent\\"}", "end_turn": false, "role": "tool"}, {"content": "", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\\"citations\\": [{\\"content\\": \\"content\\", \\"title\\": \\"title\\"}], \\"intent\\": \\"intent\\"}", "end_turn": false, "role": "tool"}, {"content": "A question\\n?", "end_turn": false, "role": "assistant"}]}]}
{"id": "response.id", "model": "some-model", "created": 0, "object": "response.object", "choices": [{"messages": [{"content": "{\\"citations\\": [{\\"content\\": \\"content\\", \\"title\\": \\"title\\"}], \\"intent\\": \\"intent\\"}", "end_turn": false, "role": "tool"}, {"content": "A question\\n?", "end_turn": true, "role": "assistant"}]}]}
"""
        )

    @patch("app.requests.Session")
    @patch("app.env_helper")
    def test_converstation_azure_byod_receives_error_from_search_when_streaming_with_data(
        self, env_helper_mock, get_requests_session_mock
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        response_mock = MockResponse(include_error=True)
        mock_session.post = Mock(return_value=response_mock)
        env_helper_mock.should_use_data.return_value = True

        # when
        response = app.test_client().post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert b'"error": "An error occurred\\n"' in response.data

    @patch("app.requests.Session")
    @patch("app.env_helper")
    def test_converstation_azure_byod_throws_exception_when_streaming_with_data(
        self, env_helper_mock, get_requests_session_mock
    ):
        # given
        mock_session = get_requests_session_mock.return_value
        mock_session.post.side_effect = ValueError("Test exception")
        env_helper_mock.should_use_data.return_value = True

        # when
        response = app.test_client().post(
            "/api/conversation/azure_byod",
            headers={"content-type": "application/json"},
            json=self.body,
        )

        # then
        assert response.status_code == 200
        assert b'{"error": "Test exception"}\n' in response.data
