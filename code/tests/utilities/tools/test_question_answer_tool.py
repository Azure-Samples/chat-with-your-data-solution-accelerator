import json
from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.answer import Answer
from backend.batch.utilities.tools.question_answer_tool import QuestionAnswerTool
from backend.batch.utilities.common.source_document import SourceDocument


@pytest.fixture(autouse=True)
def config_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.ConfigHelper"
    ) as mock:
        config = mock.get_active_config_or_default.return_value
        config.prompts.use_on_your_data_format = True
        config.prompts.answering_system_prompt = "mock answering system prompt"
        config.prompts.answering_user_prompt = (
            "Sources: {sources}, Question: {question}"
        )
        config.example.documents = json.dumps(
            {
                "retrieved_documents": [
                    {"[doc1]": {"content": "mock example content"}},
                ]
            }
        )
        config.example.user_question = "mock example user question"
        config.example.answer = "mock example answer"

        yield config


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.tools.question_answer_tool.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_OPENAI_SYSTEM_MESSAGE = "mock azure openai system message"
        env_helper.AZURE_SEARCH_TOP_K = 1
        env_helper.AZURE_SEARCH_FILTER = "mock filter"
        env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False

        yield env_helper


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.tools.question_answer_tool.LLMHelper") as mock:
        llm_helper = mock.return_value

        mock_response = MagicMock()
        mock_response.message.content = "mock content"

        llm_helper.get_chat_completion.return_value.choices = [mock_response]
        llm_helper.get_chat_completion.return_value.usage.prompt_tokens = 100
        llm_helper.get_chat_completion.return_value.usage.completion_tokens = 50

        yield llm_helper


@pytest.fixture(autouse=True)
def search_handler_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.Search.get_search_handler"
    ) as mock:
        search_handler = mock.return_value

        yield search_handler


@pytest.fixture(autouse=True)
def source_documents_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.Search.get_source_documents"
    ) as mock:
        documents = [
            SourceDocument(
                id="mock id",
                content="mock content",
                title="mock title",
                source="mock source",
                chunk=123,
                offset=123,
                page_number=123,
            ),
            SourceDocument(
                id="mock id 2",
                content="mock content 2",
                title="mock title 2",
                source="mock source 2",
                chunk_id="mock chunk id 2",
            ),
        ]
        mock.return_value = documents
        yield documents


def test_answer_question_returns_source_documents(
    source_documents_mock: list[SourceDocument],
):
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert len(answer.source_documents) == 2
    assert isinstance(answer.source_documents[0], SourceDocument)
    assert answer.source_documents == source_documents_mock


def test_answer_question_returns_answer():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert isinstance(answer, Answer)
    assert answer.question == "mock question"
    assert answer.answer == "mock content"


def test_tokens_included_in_answer():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert isinstance(answer, Answer)
    assert answer.prompt_tokens == 100
    assert answer.completion_tokens == 50


def test_correct_prompt_with_few_shot_example(llm_helper_mock: MagicMock):
    # given
    tool = QuestionAnswerTool()

    # when
    tool.answer_question("mock question", [])

    # then
    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {"content": "mock answering system prompt", "role": "system"},
            {
                "content": 'Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock example content"}}]}, Question: mock example user question',
                "name": "example_user",
                "role": "system",
            },
            {
                "content": "mock example answer",
                "name": "example_assistant",
                "role": "system",
            },
            {"content": "mock azure openai system message", "role": "system"},
            {
                "content": 'Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question',
                "role": "user",
            },
        ],
        temperature=0,
    )


@patch("backend.batch.utilities.tools.question_answer_tool.warnings.warn")
def test_correct_prompt_without_few_shot_example(
    warn_mock: MagicMock, config_mock: MagicMock, llm_helper_mock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    config_mock.example.documents = "  "
    config_mock.example.user_question = "  "

    # when
    tool.answer_question("mock question", [])

    # then
    warn_mock.assert_called_once()

    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {"content": "mock answering system prompt", "role": "system"},
            {"content": "mock azure openai system message", "role": "system"},
            {
                "content": 'Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question',
                "role": "user",
            },
        ],
        temperature=0,
    )


def test_correct_prompt_with_few_shot_example_and_chat_history(
    llm_helper_mock: MagicMock,
):
    # given
    tool = QuestionAnswerTool()
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
    ]

    # when
    tool.answer_question("mock question", chat_history)

    # then
    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {"content": "mock answering system prompt", "role": "system"},
            {
                "content": 'Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock example content"}}]}, Question: mock example user question',
                "name": "example_user",
                "role": "system",
            },
            {
                "content": "mock example answer",
                "name": "example_assistant",
                "role": "system",
            },
            {"content": "mock azure openai system message", "role": "system"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi, how can I help?"},
            {
                "content": 'Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question',
                "role": "user",
            },
        ],
        temperature=0,
    )


def test_non_on_your_data_prompt_correct(
    config_mock: MagicMock,
    llm_helper_mock: MagicMock,
):
    # given
    tool = QuestionAnswerTool()
    config_mock.prompts.use_on_your_data_format = False
    config_mock.prompts.answering_user_prompt = (
        "Sources: {sources}, Question: {question}"
    )

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert isinstance(answer, Answer)
    assert answer.question == "mock question"
    assert answer.answer == "mock content"

    llm_helper_mock.get_chat_completion.assert_called_once_with(
        [
            {
                "content": "Sources: [doc1]: mock content\n\n[doc2]: mock content 2, Question: mock question",
                "role": "user",
            },
        ],
        temperature=0,
    )


@pytest.mark.parametrize(
    "input,expected",
    [(' {"mock": "data"} ', '{"mock":"data"}'), ("invalid", "invalid")],
)
def test_json_remove_whitespace(input: str, expected: str):
    # when
    result = QuestionAnswerTool.json_remove_whitespace(input)

    # then
    assert result == expected
