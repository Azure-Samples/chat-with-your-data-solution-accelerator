import os

from unittest.mock import Mock
from unittest.mock import patch

from app import app


class TestConfig:
    def test_returns_correct_config(self):
        response = app.test_client().get("/api/config")

        assert response.status_code == 200
        assert response.json == {"azureSpeechKey": None, "azureSpeechRegion": None}


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
