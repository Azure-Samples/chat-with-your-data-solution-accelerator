from unittest.mock import patch, MagicMock

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.plugins.ChatPlugin import ChatPlugin
from semantic_kernel import Kernel


@patch("backend.batch.utilities.plugins.ChatPlugin.QuestionAnswerTool")
@pytest.mark.asyncio
async def test_search_documents(QuestionAnswerToolMock: MagicMock):
    # given
    kernel = Kernel()

    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help you today?"},
    ]
    question = "mock-question"

    plugin = kernel.add_plugin(
        plugin=ChatPlugin(question=question, chat_history=chat_history),
        plugin_name="Chat",
    )

    mock_answer = Answer(question=question, answer="mock-answer")

    QuestionAnswerToolMock.return_value.answer_question.return_value = mock_answer

    # when
    answer = await kernel.invoke(plugin["search_documents"], question=question)

    # then
    assert answer is not None
    assert answer.value == mock_answer

    QuestionAnswerToolMock.return_value.answer_question.assert_called_once_with(
        question=question,
        chat_history=chat_history,
    )


@patch("backend.batch.utilities.plugins.ChatPlugin.TextProcessingTool")
@pytest.mark.asyncio
async def test_text_processing(TextProcessingToolMock: MagicMock):
    # given
    kernel = Kernel()

    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help you today?"},
    ]
    question = "mock-question"

    plugin = kernel.add_plugin(
        plugin=ChatPlugin(question=question, chat_history=chat_history),
        plugin_name="Chat",
    )

    text = "mock-text"
    operation = "mock-operation"
    mock_answer = Answer(question=question, answer="mock-answer")

    TextProcessingToolMock.return_value.answer_question.return_value = mock_answer

    # when
    answer = await kernel.invoke(
        plugin["text_processing"],
        text=text,
        operation=operation,
    )

    # then
    assert answer is not None
    assert answer.value == mock_answer

    TextProcessingToolMock.return_value.answer_question.assert_called_once_with(
        question=question,
        chat_history=chat_history,
        text=text,
        operation=operation,
    )
