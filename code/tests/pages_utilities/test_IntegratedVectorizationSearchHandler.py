import pytest
from unittest.mock import Mock, patch
from backend.batch.utilities.search.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)


@pytest.fixture
def env_helper_mock():
    mock = Mock()
    mock.AZURE_SEARCH_SERVICE = "https://example.search.windows.net"
    mock.AZURE_SEARCH_INDEX = "example-index"
    mock.AZURE_SEARCH_KEY = "example-key"
    mock.is_auth_type_keys = Mock(return_value=True)
    return mock


@pytest.fixture
def search_client_mock():
    with patch(
        "backend.batch.utilities.search.IntegratedVectorizationSearchHandler.SearchClient"
    ) as mock:
        yield mock


@pytest.fixture
def handler(env_helper_mock, search_client_mock):
    with patch(
        "backend.batch.utilities.search.IntegratedVectorizationSearchHandler.SearchClient",
        return_value=search_client_mock,
    ):
        return IntegratedVectorizationSearchHandler(env_helper_mock)


def test_create_search_client(handler, search_client_mock):
    assert handler.create_search_client() == search_client_mock.return_value


def test_perform_search(handler, search_client_mock):
    # given
    filename = "testfile"

    # when
    handler.perform_search(filename)

    # then
    search_client_mock.search.assert_called_once_with(
        search_text="*",
        select=["id", "chunk_id", "content"],
        filter=f"title eq '{filename}'",
    )


def test_process_results(handler):
    # given
    results = [{"chunk_id": "123_chunk", "content": "some content"}]

    # when
    data = handler.process_results(results)

    # then
    assert data[0] == ["123", "some content"]


def test_delete_files(handler, search_client_mock):
    # given
    files = {"file1": ["1", "2"]}

    # when
    result = handler.delete_files(files)

    # then
    assert result == "file1"
    search_client_mock.delete_documents.assert_called_once()


def test_output_results(handler):
    # given
    results = [
        {"chunk_id": "123_chunk", "title": "file1"},
        {"chunk_id": "456_chunk", "title": "file2"},
        {"chunk_id": "789_chunk", "title": "file1"},
    ]

    # when
    files = handler.output_results(results)

    # then
    assert files == {
        "file1": ["123_chunk", "789_chunk"],
        "file2": ["456_chunk"],
    }


def test_get_files(handler, search_client_mock):
    # given
    results = [
        {"id": "1", "chunk_id": "123_chunk", "title": "file1"},
        {"id": "2", "chunk_id": "456_chunk", "title": "file2"},
        {"id": "3", "chunk_id": "789_chunk", "title": "file1"},
    ]
    search_client_mock.search.return_value = results

    # when
    files = handler.get_files()

    # then
    assert files == results
    search_client_mock.search.assert_called_once_with(
        "*", select="id, chunk_id, title", include_total_count=True
    )
