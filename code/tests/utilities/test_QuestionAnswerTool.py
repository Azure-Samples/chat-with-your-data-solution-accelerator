import json
from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.tools.QuestionAnswerTool import QuestionAnswerTool
from langchain_core.documents import Document


@pytest.fixture(autouse=True)
def azure_search_handler_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.AzureSearchHandler"
    ) as mock:
        query_search = mock.return_value.query_search
        document = Document("mock content")
        document.metadata = {
            "id": "mock id",
            "title": "mock title",
            "source": "mock source",
            "chunk": "mock chunk",
            "offset": "mock offset",
            "page_number": "mock page number",
        }
        documents = [document]
        query_search.return_value = documents
        yield query_search


@pytest.fixture(autouse=True)
def integrated_vectorization_search_handler_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.IntegratedVectorizationSearchHandler"
    ) as mock:
        query_search = mock.return_value.query_search
        query_search.return_value = [
            {
                "id": "mock id 1",
                "title": "mock title 1",
                "source": "https://example.com/doc1",
                "chunk_id": "mock chunk id 1",
                "content": "mock content 1",
            },
            {
                "id": "mock id 2",
                "title": "mock title 2",
                "source": "https://example.com/doc2",
                "chunk_id": "mock chunk id 2",
                "content": "mock content 2",
            },
        ]
        yield query_search


@pytest.fixture(autouse=True)
def config_mock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.ConfigHelper") as mock:
        config = mock.get_active_config_or_default.return_value
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
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_OPENAI_SYSTEM_MESSAGE = "mock azure openai system message"
        env_helper.AZURE_SEARCH_TOP_K = 1
        env_helper.AZURE_SEARCH_FILTER = "mock filter"
        env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False

        yield env_helper


@pytest.fixture(autouse=True)
def LLMHelperMock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.LLMHelper") as mock:
        yield mock


@pytest.fixture(autouse=True)
def LLMChainMock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.LLMChain") as mock:
        mock.return_value.return_value = {"text": "mock content"}

        yield mock


@pytest.fixture(autouse=True)
def get_openai_callback_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.get_openai_callback"
    ) as mock:
        yield mock


def test_answer_question_returns_source_documents():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    source_documents = answer.source_documents

    assert len(source_documents) == 1

    assert source_documents[0].id == "mock id"
    assert source_documents[0].title == "mock title"
    assert source_documents[0].source == "mock source"
    assert source_documents[0].chunk == "mock chunk"
    assert source_documents[0].offset == "mock offset"
    assert source_documents[0].page_number == "mock page number"


def test_answer_question_integrated_vectorization(env_helper_mock: MagicMock):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    source_documents = answer.source_documents

    assert len(source_documents) == 2

    assert source_documents[0].chunk_id == "mock chunk id 1"
    assert source_documents[0].title == "mock title 1"
    assert (
        source_documents[0].source == "https://example.com/doc1_SAS_TOKEN_PLACEHOLDER_"
    )
    assert source_documents[0].content == "mock content 1"


def test_answer_question_returns_answer():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert isinstance(answer, Answer)
    assert answer.question == "mock question"
    assert answer.answer == "mock content"


def test_get_openai_callback(get_openai_callback_mock: MagicMock):
    # given
    cb = get_openai_callback_mock.return_value.__enter__.return_value
    cb.prompt_tokens = 100
    cb.completion_tokens = 50
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    get_openai_callback_mock.assert_called_once()
    assert answer.prompt_tokens == 100
    assert answer.completion_tokens == 50


def test_correct_prompt_with_few_shot_example(
    LLMHelperMock: MagicMock, LLMChainMock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    llm = LLMHelperMock.return_value.get_llm.return_value
    answer_generator = LLMChainMock.return_value

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "question": "mock question",
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}',
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    assert LLMChainMock.call_args[1]["llm"] == llm
    assert LLMChainMock.call_args[1]["verbose"] is True

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock example content"}}]}, Question: mock example user question
AI: mock example answer
System: mock azure openai system message
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}, Question: mock question"""
    )


def test_correct_prompt_without_few_shot_example(
    config_mock: MagicMock, LLMChainMock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    config_mock.example.documents = "  "
    config_mock.example.user_question = "  "

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "question": "mock question",
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}',
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
System: mock azure openai system message
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}, Question: mock question"""
    )


def test_correct_prompt_with_few_shot_example_and_chat_history(LLMChainMock: MagicMock):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
    ]

    # when
    tool.answer_question("mock question", chat_history)

    # then
    expected_input = {
        "question": "mock question",
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}',
        "chat_history": chat_history,
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock example content"}}]}, Question: mock example user question
AI: mock example answer
System: mock azure openai system message
Human: Hello
AI: Hi, how can I help?
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}}]}, Question: mock question"""
    )


def test_non_on_your_data_prompt_correct(
    config_mock: MagicMock, LLMChainMock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    config_mock.prompts.use_on_your_data_format = False
    config_mock.prompts.answering_user_prompt = (
        "Sources: {sources}, Question: {question}"
    )

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "sources": """[doc1]: mock content""",
        "question": "mock question",
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert prompt_test == """Sources: [doc1]: mock content, Question: mock question"""


@pytest.mark.parametrize(
    "input,expected",
    [(' {"mock": "data"} ', '{"mock":"data"}'), ("invalid", "invalid")],
)
def test_json_remove_whitespace(input: str, expected: str):
    # when
    result = QuestionAnswerTool.json_remove_whitespace(input)

    # then
    assert result == expected


def test_generate_source_documents():
    # given
    search_results = [
        {
            "id": "mock id 1",
            "title": "mock title 1",
            "source": "https://strr73dnzv4fabcd.blob.core.windows.net/documents/https://example.com/doc1",
            "chunk_id": "mock chunk id 1",
            "content": "mock content 1",
        },
        {
            "id": "mock id 2",
            "title": "mock title 2",
            "source": "https://example.com/doc2",
            "chunk_id": "mock chunk id 2",
            "content": "mock content 2",
        },
    ]

    # when
    sources = QuestionAnswerTool().generate_source_documents(search_results)

    # then
    assert len(sources) == 2

    assert sources[0].metadata == {
        "id": "mock id 1",
        "title": "mock title 1",
        "source": "https://example.com/doc1",
        "chunk_id": "mock chunk id 1",
    }
    assert sources[0].page_content == "mock content 1"

    assert sources[1].metadata == {
        "id": "mock id 2",
        "title": "mock title 2",
        "source": "https://example.com/doc2_SAS_TOKEN_PLACEHOLDER_",
        "chunk_id": "mock chunk id 2",
    }
    assert sources[1].page_content == "mock content 2"
