import pytest
from unittest.mock import Mock, patch
from backend.batch.utilities.search.AzureSearchHandler import AzureSearchHandler
from langchain_core.documents import Document
import json


@pytest.fixture
def env_helper_mock():
    mock = Mock()
    mock.AZURE_SEARCH_SERVICE = "https://example.search.windows.net"
    mock.AZURE_SEARCH_INDEX = "example-index"
    mock.AZURE_SEARCH_KEY = "example-key"
    mock.is_auth_type_keys = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_azure_search_helper():
    with patch(
        "backend.batch.utilities.search.AzureSearchHandler.AzureSearchHelper"
    ) as mock:
        vector_store = mock.return_value.get_vector_store.return_value.client
        yield vector_store


@pytest.fixture
def mock_vector_store():
    with patch(
        "backend.batch.utilities.search.AzureSearchHandler.AzureSearchHelper"
    ) as mock:
        vector_store = mock.return_value.get_vector_store.return_value
        yield vector_store


@pytest.fixture
def handler(env_helper_mock, mock_azure_search_helper):
    with patch(
        "backend.batch.utilities.search.AzureSearchHandler.AzureSearchHelper",
        return_value=mock_azure_search_helper,
    ):
        return AzureSearchHandler(env_helper_mock)


def test_create_search_client(handler, mock_azure_search_helper):
    # when
    search_client = handler.create_search_client()

    # then
    assert search_client == mock_azure_search_helper


def test_process_results(handler):
    # given
    results = [{"metadata": json.dumps({"chunk": 1}), "content": "Content 1"}]

    # when
    data = handler.process_results(results)

    # then
    assert data[0] == [1, "Content 1"]


def test_delete_files(handler):
    # given
    files = {"file1": ["1", "2"]}

    # when
    result = handler.delete_files(files)

    # then
    assert result == "file1"
    handler.search_client.delete_documents.assert_called_once()


def test_output_results(handler):
    # given
    results = [
        {"id": 1, "title": "file1"},
        {"id": 2, "title": "file2"},
        {"id": 3, "title": "file1"},
        {"id": 4, "title": "file3"},
    ]

    # when
    files = handler.output_results(results)

    # then
    assert files == {
        "file1": [1, 3],
        "file2": [2],
        "file3": [4],
    }


def test_get_files(handler):
    # given
    results = [
        {"id": 1, "title": "file1"},
        {"id": 2, "title": "file2"},
        {"id": 3, "title": "file3"},
    ]
    handler.search_client.search.return_value = results

    # when
    files = handler.get_files()

    # then
    assert files == results
    handler.search_client.search.assert_called_once_with(
        "*", select="id, title", include_total_count=True
    )


def test_query_search(handler, mock_vector_store):
    # given
    question = "What is the answer?"

    # when
    result = handler.query_search(question)

    # then
    mock_vector_store.similarity_search.assert_called_once_with(
        query=question,
        k=handler.env_helper.AZURE_SEARCH_TOP_K,
        filters=handler.env_helper.AZURE_SEARCH_FILTER,
    )
    assert result == mock_vector_store.similarity_search.return_value


def test_return_answer_source_documents(handler):
    # given
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
    # when
    source_documents = handler.return_answer_source_documents(documents)

    # then
    assert len(source_documents) == 1
    assert source_documents[0].id == "mock id"
    assert source_documents[0].content == "mock content"
    assert source_documents[0].title == "mock title"
    assert source_documents[0].source == "mock source"
