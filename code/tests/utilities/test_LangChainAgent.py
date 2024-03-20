from unittest.mock import MagicMock

from backend.batch.utilities.orchestrator.LangChainAgent import LangChainAgent
from backend.batch.utilities.common.Answer import Answer


class Testing_LangChainAgent(LangChainAgent):
    def __init__(self) -> None:
        self.content_safety_checker = MagicMock()
        self.question_answer_tool = MagicMock()
        self.text_processing_tool = MagicMock()


def test_run_tool_returns_answer_json():
    # Given
    user_message = "Hello"
    agent = Testing_LangChainAgent()
    answer = Answer(
        question=user_message,
        answer="Hello, how can I help you?",
        source_documents=[],
        prompt_tokens=None,
        completion_tokens=None,
    )
    agent.question_answer_tool.answer_question = MagicMock(return_value=answer)

    # When
    answer_json = agent.run_tool(user_message)

    # Then
    assert (
        answer_json
        == '{"question": "Hello", "answer": "Hello, how can I help you?", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'
    )
    agent.question_answer_tool.answer_question.assert_called_once_with(
        user_message, chat_history=[]
    )


def test_run_text_processing_tool_returns_answer_json():
    # Given
    user_message = "Hello"
    agent = Testing_LangChainAgent()
    answer = Answer(
        question=user_message,
        answer="Hello, how can I help you?",
        source_documents=[],
        prompt_tokens=None,
        completion_tokens=None,
    )
    agent.text_processing_tool.answer_question = MagicMock(return_value=answer)

    # When
    answer_json = agent.run_text_processing_tool(user_message)

    # Then
    assert (
        answer_json
        == '{"question": "Hello", "answer": "Hello, how can I help you?", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'
    )
    agent.text_processing_tool.answer_question.assert_called_once_with(
        user_message, chat_history=[]
    )
