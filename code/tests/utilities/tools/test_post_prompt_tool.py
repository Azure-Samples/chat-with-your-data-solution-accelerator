from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.answer import Answer
from backend.batch.utilities.common.source_document import SourceDocument
from backend.batch.utilities.tools.post_prompt_tool import PostPromptTool


@pytest.fixture(autouse=True)
def config_mock():
    with patch("backend.batch.utilities.tools.post_prompt_tool.ConfigHelper") as mock:
        config = mock.get_active_config_or_default.return_value
        config.prompts.post_answering_prompt = "mock\n{question}\n{answer}\n{sources}"
        config.messages.post_answering_filter = "mock filter"

        yield config


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.tools.post_prompt_tool.LLMHelper") as mock:
        llm_helper = mock.return_value

        mock_response = MagicMock()
        mock_response.message.content = "true"

        llm_helper.get_chat_completion.return_value.choices = [mock_response]
        llm_helper.get_chat_completion.return_value.usage.prompt_tokens = 10
        llm_helper.get_chat_completion.return_value.usage.completion_tokens = 20

        yield llm_helper


@pytest.fixture
def answer():
    return Answer(
        question="user question",
        answer="answer",
        source_documents=[
            SourceDocument(
                id="id",
                content="content",
                source="source",
                title="title",
                chunk=1,
                offset=1,
                page_number=1,
                chunk_id="chunk_id",
            )
        ],
        prompt_tokens=100,
        completion_tokens=100,
    )


def test_validate_answer_without_filtering(llm_helper_mock: MagicMock, answer: Answer):
    # when
    result = PostPromptTool().validate_answer(answer)

    # then
    assert result == Answer(
        question="user question",
        answer="answer",
        source_documents=[
            SourceDocument(
                id="id",
                content="content",
                source="source",
                title="title",
                chunk=1,
                offset=1,
                page_number=1,
                chunk_id="chunk_id",
            )
        ],
        prompt_tokens=10,
        completion_tokens=20,
    )

    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {
                "role": "user",
                "content": "mock\nuser question\nanswer\n[doc1]: content",
            }
        ]
    )


def test_validate_answer_with_filtering(llm_helper_mock: MagicMock, answer: Answer):
    # given
    llm_helper_mock.get_chat_completion.return_value.choices[0].message.content = (
        "false"
    )

    # when
    result = PostPromptTool().validate_answer(answer)

    # then
    assert result == Answer(
        question="user question",
        answer="mock filter",
        source_documents=[],
        prompt_tokens=10,
        completion_tokens=20,
    )

    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {
                "role": "user",
                "content": "mock\nuser question\nanswer\n[doc1]: content",
            }
        ]
    )
