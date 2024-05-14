from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.orchestrator.orchestrator_base import OrchestratorBase


class MockOrchestrator(OrchestratorBase):
    async def orchestrate(
        self, user_message: str, chat_history: list[dict], **kwargs: dict
    ):
        return []


@pytest.fixture(autouse=True)
def config_mock():
    with patch(
        "backend.batch.utilities.orchestrator.orchestrator_base.ConfigHelper"
    ) as mock:
        config = mock.get_active_config_or_default.return_value
        yield config


@pytest.fixture(autouse=True)
def conversation_logger_mock():
    with patch(
        "backend.batch.utilities.orchestrator.orchestrator_base.ConversationLogger"
    ) as mock:
        conversation_logger = mock.return_value
        yield conversation_logger


@pytest.fixture(autouse=True)
def content_safety_checker_mock():
    with patch(
        "backend.batch.utilities.orchestrator.orchestrator_base.ContentSafetyChecker"
    ) as mock:
        content_safety_checker = mock.return_value
        yield content_safety_checker


def test_call_content_safety_input_replace(content_safety_checker_mock: MagicMock):
    # given
    orchestrator = MockOrchestrator()
    content_safety_checker_mock.validate_input_and_replace_if_harmful.return_value = (
        "filtered user message"
    )

    # when
    result = orchestrator.call_content_safety_input("user message")

    # then
    assert result == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "user message"}',
            "end_turn": False,
        },
        {"role": "assistant", "content": "filtered user message", "end_turn": True},
    ]


def test_call_content_safety_input_no_replace(content_safety_checker_mock: MagicMock):
    # given
    orchestrator = MockOrchestrator()
    content_safety_checker_mock.validate_input_and_replace_if_harmful.return_value = (
        "user message"
    )

    # when
    result = orchestrator.call_content_safety_input("user message")

    # then
    assert result is None


def test_call_content_safety_output_replace(content_safety_checker_mock: MagicMock):
    # given
    orchestrator = MockOrchestrator()
    content_safety_checker_mock.validate_output_and_replace_if_harmful.return_value = (
        "filtered answer"
    )

    # when
    result = orchestrator.call_content_safety_output("user message", "answer")

    # then
    assert result == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "user message"}',
            "end_turn": False,
        },
        {"role": "assistant", "content": "filtered answer", "end_turn": True},
    ]


def test_call_content_safety_output_no_replace(content_safety_checker_mock: MagicMock):
    # given
    orchestrator = MockOrchestrator()
    content_safety_checker_mock.validate_output_and_replace_if_harmful.return_value = (
        "answer"
    )

    # when
    result = orchestrator.call_content_safety_output("user message", "answer")

    # then
    assert result is None
