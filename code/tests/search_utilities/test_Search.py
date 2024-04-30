import pytest
from unittest.mock import Mock, MagicMock, patch
from backend.batch.utilities.search.Search import Search
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
    mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False
    return mock


@pytest.fixture(autouse=True)
def iv_search_handler_mock():
    with patch(
        "backend.batch.utilities.search.IntegratedVectorizationSearchHandler"
    ) as mock:
        yield mock


def test_get_search_handler_integrated_vectorization(
    env_helper_mock, iv_search_handler_mock
):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True

    # when
    search_handler = Search.get_search_handler(env_helper_mock)

    # then
    assert isinstance(search_handler, IntegratedVectorizationSearchHandler)


@patch("backend.batch.utilities.search.Search")
def test_get_source_documents_integrated_vectorization(search_handler_mock: MagicMock):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True
    question = "example question"

    search_results = [
        {
            "id": 1,
            "title": "Example Title 1",
            "source": "https://example.com/1",
            "chunk_id": "chunk1",
        },
        {
            "id": 2,
            "title": "Example Title 2",
            "source": "https://example.com/2",
            "chunk_id": "chunk2",
        },
    ]
    search_handler_mock.query_search.return_value = search_results

    # when
    source_documents = Search.get_source_documents(search_handler_mock, question)

    # then
    assert len(source_documents) == len(search_results)


@patch("backend.batch.utilities.search.Search")
def test_get_source_documents_azure_search(search_handler_mock: MagicMock):
    # given
    question = "example question"

    search_results = [
        {
            "id": 1,
            "title": "Example Title 1",
            "source": "https://example.com/1",
            "chunk_id": "chunk1",
        },
        {
            "id": 2,
            "title": "Example Title 2",
            "source": "https://example.com/2",
            "chunk_id": "chunk2",
        },
    ]
    search_handler_mock.query_search.return_value = search_results

    # when
    source_documents = Search.get_source_documents(search_handler_mock, question)

    # then
    assert len(source_documents) == len(search_results)


def test_generate_source_documents():
    # given
    search_results = [
        {
            "id": 1,
            "title": "Example Title 1",
            "source": "https://example.com/1",
            "chunk_id": "chunk1",
            "content": "mock content 1",
        },
        {
            "id": 2,
            "title": "Example Title 2",
            "source": "https://example.com/2",
            "chunk_id": "chunk2",
            "content": "mock content 2",
        },
    ]

    # when
    source_documents = Search.generate_source_documents(search_results)

    # then
    assert len(source_documents) == len(search_results)


def test__extract_source_url_multiple_http():
    # given
    original_source = "https://example.com/http://example.com"

    # when
    source_url = Search._extract_source_url(original_source)

    # then
    assert source_url == "http://example.com"


def test__extract_source_url_single_http():
    # given
    original_source = "https://example.com"

    # when
    source_url = Search._extract_source_url(original_source)

    # then
    assert source_url == "https://example.com_SAS_TOKEN_PLACEHOLDER_"
