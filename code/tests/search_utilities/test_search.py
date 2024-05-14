import pytest
from unittest.mock import Mock, MagicMock, patch
from backend.batch.utilities.search.search import Search
from backend.batch.utilities.search.integrated_vectorization_search_handler import (
    IntegratedVectorizationSearchHandler,
)
from backend.batch.utilities.common.source_document import SourceDocument


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
        "backend.batch.utilities.search.integrated_vectorization_search_handler"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_index_mock():
    with patch.object(
        IntegratedVectorizationSearchHandler, "_check_index_exists", return_value=True
    ) as mock:
        yield mock


def test_get_search_handler_integrated_vectorization(env_helper_mock):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True

    # when
    search_handler = Search.get_search_handler(env_helper_mock)

    # then
    assert isinstance(search_handler, IntegratedVectorizationSearchHandler)


def test_get_source_documents_integrated_vectorization(env_helper_mock):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True
    question = "example question"

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
    search_handler_mock = Mock(spec=IntegratedVectorizationSearchHandler)
    search_handler_mock.query_search.return_value = search_results

    # when
    source_documents = Search.get_source_documents(search_handler_mock, question)

    # then
    assert len(source_documents) == len(search_results)


def test_get_source_documents_integrated_vectorization_no_results(env_helper_mock):
    # given
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True
    question = "example question"

    search_results = []
    search_handler_mock = Mock(spec=IntegratedVectorizationSearchHandler)
    search_handler_mock.query_search.return_value = search_results

    # when
    source_documents = Search.get_source_documents(search_handler_mock, question)

    # then
    assert len(source_documents) == len(search_results)


@patch("backend.batch.utilities.search.search")
def test_get_source_documents_azure_search(search_handler_mock: MagicMock):
    # given
    question = "example question"

    expected_source_documents = [
        SourceDocument(
            id=1,
            content="content1",
            title="title1",
            source="source1",
            chunk="chunk1",
            offset="offset1",
            page_number="page_number1",
        ),
        SourceDocument(
            id=2,
            content="content2",
            title="title2",
            source="source2",
            chunk="chunk2",
            offset="offset2",
            page_number="page_number2",
        ),
    ]
    search_handler_mock.query_search.return_value = expected_source_documents

    # when
    actual_source_documents = Search.get_source_documents(search_handler_mock, question)

    # then
    assert len(actual_source_documents) == len(expected_source_documents)
