import json
from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.answer import Answer
from backend.batch.utilities.tools.question_answer_tool import QuestionAnswerTool
from langchain_core.documents import Document
from backend.batch.utilities.common.source_document import SourceDocument


@pytest.fixture(autouse=True)
def config_mock():
    with patch("backend.batch.utilities.tools.question_answer_tool.ConfigHelper") as mock:
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
    with patch("backend.batch.utilities.tools.question_answer_tool.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_OPENAI_SYSTEM_MESSAGE = "mock azure openai system message"
        env_helper.AZURE_SEARCH_TOP_K = 1
        env_helper.AZURE_SEARCH_FILTER = "mock filter"
        env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False

        yield env_helper


@pytest.fixture(autouse=True)
def LLMHelperMock():
    with patch("backend.batch.utilities.tools.question_answer_tool.LLMHelper") as mock:
        yield mock


@pytest.fixture(autouse=True)
def LLMChainMock():
    with patch("backend.batch.utilities.tools.question_answer_tool.LLMChain") as mock:
        mock.return_value.return_value = {"text": "mock content"}

        yield mock


@pytest.fixture(autouse=True)
def get_openai_callback_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.get_openai_callback"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def get_search_handler_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.Search.get_search_handler"
    ) as mock:
        search_handler = mock.return_value

        yield search_handler


@pytest.fixture(autouse=True)
def get_source_documents_mock():
    with patch(
        "backend.batch.utilities.tools.question_answer_tool.Search.get_source_documents"
    ) as mock:
        source_documents = mock.return_value
        yield source_documents


@pytest.fixture(autouse=True)
def get_source_documents_yield():
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
        yield mock


def test_answer_question_returns_source_documents():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    source_documents = answer.source_documents

    assert len(source_documents) == 2

    assert source_documents[0].id == "mock id"
    assert source_documents[0].title == "mock title"
    assert source_documents[0].content == "mock content"
    assert source_documents[0].source == "mock source"
    assert source_documents[0].chunk == 123
    assert source_documents[0].offset == 123
    assert source_documents[0].page_number == 123

    assert source_documents[1].id == "mock id 2"
    assert source_documents[1].title == "mock title 2"
    assert source_documents[1].content == "mock content 2"

    assert source_documents[1].source == "mock source 2"
    assert source_documents[1].chunk_id == "mock chunk id 2"


def test_answer_question_returns_answer(
    get_search_handler_mock, get_source_documents_yield
):
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
    LLMHelperMock: MagicMock, LLMChainMock: MagicMock, get_source_documents_yield
):
    # given
    tool = QuestionAnswerTool()
    llm = LLMHelperMock.return_value.get_llm.return_value
    answer_generator = LLMChainMock.return_value

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}',
        "question": "mock question",
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
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question"""
    )


def test_correct_prompt_without_few_shot_example(
    config_mock: MagicMock,
    LLMChainMock: MagicMock,
    get_search_handler_mock,
    get_source_documents_yield,
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
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}',
        "question": "mock question",
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
System: mock azure openai system message
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question"""
    )


def test_correct_prompt_with_few_shot_example_and_chat_history(
    LLMChainMock: MagicMock, get_search_handler_mock, get_source_documents_yield
):
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
        "sources": '{"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}',
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
Human: Sources: {"retrieved_documents":[{"[doc1]":{"content":"mock content"}},{"[doc2]":{"content":"mock content 2"}}]}, Question: mock question"""
    )


def test_non_on_your_data_prompt_correct(
    config_mock: MagicMock,
    LLMChainMock: MagicMock,
    get_search_handler_mock,
    get_source_documents_yield,
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
        "sources": """[doc1]: mock content\n\n[doc2]: mock content 2""",
        "question": "mock question",
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """Sources: [doc1]: mock content\n\n[doc2]: mock content 2, Question: mock question"""
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


def create_document_and_source_documents(
    get_source_documents_mock, get_search_handler_mock
):
    document = Document("mock content")
    document.metadata = {
        "id": "mock id",
        "title": "mock title",
        "source": "mock source",
        "chunk": "mock chunk",
        "offset": "mock offset",
        "page_number": "mock page number",
    }
    get_source_documents_mock.return_value = document
    documents = []
    documents.append(
        SourceDocument(
            id=document.metadata["id"],
            content=document.page_content,
            title=document.metadata["title"],
            source=document.metadata["source"],
            chunk=document.metadata["chunk"],
            offset=document.metadata["offset"],
            page_number=document.metadata["page_number"],
        )
    )
    get_search_handler_mock.return_answer_source_documents.return_value = documents
