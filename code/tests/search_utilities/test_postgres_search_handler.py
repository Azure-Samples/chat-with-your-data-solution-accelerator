import json
import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.common.source_document import SourceDocument
from backend.batch.utilities.search.postgres_search_handler import AzurePostgresHandler


@pytest.fixture(autouse=True)
def env_helper_mock():
    mock = MagicMock()
    mock.POSTGRESQL_USER = "test_user"
    mock.POSTGRESQL_PASSWORD = "test_password"
    mock.POSTGRESQL_HOST = "test_host"
    mock.POSTGRESQL_DB = "test_db"
    return mock


@pytest.fixture(autouse=True)
def mock_search_client():
    with patch(
        "backend.batch.utilities.search.postgres_search_handler.AzurePostgresHelper"
    ) as mock:
        search_client = mock.return_value.get_search_client.return_value
        yield search_client


@pytest.fixture
def handler(env_helper_mock, mock_search_client):
    with patch(
        "backend.batch.utilities.search.postgres_search_handler",
        return_value=mock_search_client,
    ):
        return AzurePostgresHandler(env_helper_mock)


def test_query_search(handler, mock_search_client):
    mock_llm_helper = MagicMock()
    mock_search_client.llm_helper = mock_llm_helper

    mock_llm_helper.generate_embeddings.return_value = [1, 2, 3]

    mock_search_client.get_vector_store.return_value = [
        {
            "id": "1",
            "title": "Title1",
            "chunk": "Chunk1",
            "offset": 0,
            "page_number": 1,
            "content": "Content1",
            "source": "Source1",
        },
        {
            "id": "2",
            "title": "Title2",
            "chunk": "Chunk2",
            "offset": 1,
            "page_number": 2,
            "content": "Content2",
            "source": "Source2",
        },
    ]

    mock_search_client.get_search_client.return_value = mock_search_client
    handler.azure_postgres_helper = mock_search_client

    result = handler.query_search("Sample question")

    mock_llm_helper.generate_embeddings.assert_called_once_with("Sample question")
    mock_search_client.get_vector_store.assert_called_once()
    assert len(result) == 2
    assert isinstance(result[0], SourceDocument)
    assert result[0].id == "1"
    assert result[0].title == "Title1"
    assert result[1].content == "Content2"


def test_convert_to_source_documents(handler):
    search_results = [
        {
            "id": "1",
            "title": "Title1",
            "chunk": "Chunk1",
            "offset": 0,
            "page_number": 1,
            "content": "Content1",
            "source": "Source1",
        },
        {
            "id": "2",
            "title": "Title2",
            "chunk": "Chunk2",
            "offset": 1,
            "page_number": 2,
            "content": "Content2",
            "source": "Source2",
        },
    ]

    result = handler._convert_to_source_documents(search_results)

    assert len(result) == 2
    assert result[0].id == "1"
    assert result[0].content == "Content1"
    assert result[1].page_number == 2


def test_create_search_client(handler, mock_search_client):
    handler.azure_postgres_helper.get_search_client = MagicMock(
        return_value=mock_search_client
    )

    result = handler.create_search_client()

    assert result == mock_search_client


def test_get_files(handler):
    mock_get_files = MagicMock(return_value=["test1.txt", "test2.txt"])
    handler.azure_postgres_helper.get_files = mock_get_files

    result = handler.get_files()

    assert len(result) == 2
    assert result[0] == "test1.txt"
    assert result[1] == "test2.txt"


def test_output_results(handler):
    results = [
        {"id": "1", "title": "file1.txt"},
        {"id": "2", "title": "file2.txt"},
        {"id": "3", "title": "file1.txt"},
        {"id": "4", "title": "file3.txt"},
        {"id": "5", "title": "file2.txt"},
    ]

    expected_output = {
        "file1.txt": ["1", "3"],
        "file2.txt": ["2", "5"],
        "file3.txt": ["4"],
    }

    result = handler.output_results(results)

    assert result == expected_output
    assert len(result) == 3
    assert "file1.txt" in result
    assert result["file2.txt"] == ["2", "5"]


def test_process_results(handler):
    results = [
        {"metadata": json.dumps({"chunk": "Chunk1"}), "content": "Content1"},
        {"metadata": json.dumps({"chunk": "Chunk2"}), "content": "Content2"},
    ]
    expected_output = [["Chunk1", "Content1"], ["Chunk2", "Content2"]]
    result = handler.process_results(results)
    assert result == expected_output


def test_process_results_none(handler):
    result = handler.process_results(None)
    assert result == []


def test_process_results_missing_chunk(handler):
    results = [
        {"metadata": json.dumps({}), "content": "Content1"},
        {"metadata": json.dumps({"chunk": "Chunk2"}), "content": "Content2"},
    ]
    expected_output = [[0, "Content1"], ["Chunk2", "Content2"]]
    result = handler.process_results(results)
    assert result == expected_output


def test_delete_files(handler):
    files_to_delete = {"test1.txt": [1, 2], "test2.txt": [3]}
    mock_delete_documents = MagicMock()
    handler.azure_postgres_helper.delete_documents = mock_delete_documents

    result = handler.delete_files(files_to_delete)

    mock_delete_documents.assert_called_once_with([{"id": 1}, {"id": 2}, {"id": 3}])
    assert "test1.txt" in result


# Test case for delete_from_index method
def test_delete_from_index(handler):
    blob_url = "https://example.com/blob"

    # Mocking methods
    mock_search_by_blob_url = MagicMock(return_value=[{"id": "1", "title": "Title1"}])
    mock_output_results = MagicMock(return_value={"test1.txt": ["1"]})
    mock_delete_files = MagicMock(return_value="test1.txt")

    handler.search_by_blob_url = mock_search_by_blob_url
    handler.output_results = mock_output_results
    handler.delete_files = mock_delete_files

    handler.delete_from_index(blob_url)

    mock_search_by_blob_url.assert_called_once_with(blob_url)
    mock_output_results.assert_called_once()
    mock_delete_files.assert_called_once_with({"test1.txt": ["1"]})


# Test case for get_unique_files method
def test_get_unique_files(handler):
    mock_get_unique_files = MagicMock(
        return_value=[{"title": "test1.txt"}, {"title": "test2.txt"}]
    )
    handler.azure_postgres_helper.get_unique_files = mock_get_unique_files

    result = handler.get_unique_files()

    assert len(result) == 2
    assert result[0] == "test1.txt"
    assert result[1] == "test2.txt"
