import json
from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.tools.QuestionAnswerTool import QuestionAnswerTool
from langchain_core.documents import Document


@pytest.fixture(autouse=True)
def vector_store_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.AzureSearchHelper"
    ) as mock:
        vector_store = mock.return_value.get_vector_store.return_value

        documents = []
        for i in range(4):
            document = Document(f"mock content {i}")
            document.metadata = {
                "id": f"mock id {i}",
                "title": f"mock title {i}",
                "source": f"mock source {i}",
                "chunk": f"mock chunk {i}",
                "offset": f"mock offset {i}",
                "page_number": f"mock page number {i}",
            }
            documents.append(document)

        vector_store.similarity_search.return_value = documents

        yield vector_store


@pytest.fixture(autouse=True)
def config_mock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.ConfigHelper") as mock:
        config = mock.get_active_config_or_default.return_value
        config.prompts.answering_system_prompt = "mock answering system prompt"
        config.prompts.answering_user_prompt = (
            "Documents: {documents}, User Question: {user_question}"
        )
        config.prompts.answering_prompt = ""
        config.example.documents = json.dumps(
            {
                "retrieved_documents": [
                    {"[doc1]": {"content": "mock example content 0"}},
                    {"[doc2]": {"content": "mock example content 1"}},
                    {"[doc3]": {"content": "mock example content 2"}},
                    {"[doc4]": {"content": "mock example content 3"}},
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


def test_similarity_search_is_called(vector_store_mock: MagicMock):
    # given
    tool = QuestionAnswerTool()

    # when
    tool.answer_question("mock question", [])

    # then
    vector_store_mock.similarity_search.assert_called_once_with(
        query="mock question", k=4, search_type="hybrid"
    )


def test_answer_question_returns_source_documents():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    source_documents = answer.source_documents

    assert len(source_documents) == 4

    for i, source_document in enumerate(source_documents):
        assert source_document.id == f"mock id {i}"
        assert source_document.title == f"mock title {i}"
        assert source_document.source == f"mock source {i}"
        assert source_document.chunk == f"mock chunk {i}"
        assert source_document.offset == f"mock offset {i}"
        assert source_document.page_number == f"mock page number {i}"


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
        "user_question": "mock question",
        "documents": '{"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}',
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
Human: Documents: {"retrieved_documents":[{"[doc1]":{"content":"mock example content 0"}},{"[doc2]":{"content":"mock example content 1"}},{"[doc3]":{"content":"mock example content 2"}},{"[doc4]":{"content":"mock example content 3"}}]}, User Question: mock example user question
AI: mock example answer
System: mock azure openai system message
Human: Documents: {"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}, User Question: mock question"""
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
        "user_question": "mock question",
        "documents": '{"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}',
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
System: mock azure openai system message
Human: Documents: {"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}, User Question: mock question"""
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
        "user_question": "mock question",
        "documents": '{"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}',
        "chat_history": chat_history,
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
Human: Documents: {"retrieved_documents":[{"[doc1]":{"content":"mock example content 0"}},{"[doc2]":{"content":"mock example content 1"}},{"[doc3]":{"content":"mock example content 2"}},{"[doc4]":{"content":"mock example content 3"}}]}, User Question: mock example user question
AI: mock example answer
System: mock azure openai system message
Human: Hello
AI: Hi, how can I help?
Human: Documents: {"retrieved_documents":[{"[doc1]":{"content":"mock content 0"}},{"[doc2]":{"content":"mock content 1"}},{"[doc3]":{"content":"mock content 2"}},{"[doc4]":{"content":"mock content 3"}}]}, User Question: mock question"""
    )


def test_legacy_correct_prompt(config_mock: MagicMock, LLMChainMock: MagicMock):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    config_mock.prompts.answering_prompt = "Sources: {sources}, Question: {question}"

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "question": "mock question",
        "sources": """[doc1]: mock content 0

[doc2]: mock content 1

[doc3]: mock content 2

[doc4]: mock content 3""",
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """Sources: [doc1]: mock content 0

[doc2]: mock content 1

[doc3]: mock content 2

[doc4]: mock content 3, Question: mock question"""
    )
