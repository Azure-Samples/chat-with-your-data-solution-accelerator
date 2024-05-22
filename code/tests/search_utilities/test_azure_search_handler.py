import pytest
from unittest.mock import MagicMock, Mock, patch
from backend.batch.utilities.search.azure_search_handler import AzureSearchHandler
import json
from azure.search.documents.models import VectorizedQuery

from backend.batch.utilities.common.source_document import SourceDocument


@pytest.fixture(autouse=True)
def env_helper_mock():
    mock = Mock()
    mock.AZURE_SEARCH_USE_SEMANTIC_SEARCH = False
    mock.USE_ADVANCED_IMAGE_PROCESSING = False
    mock.AZURE_SEARCH_TOP_K = 3
    mock.AZURE_SEARCH_FILTER = "some-search-filter"
    return mock


@pytest.fixture(autouse=True)
def mock_search_client():
    with patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper"
    ) as mock:
        search_client = mock.return_value.get_search_client.return_value
        yield search_client


@pytest.fixture(autouse=True)
def mock_llm_helper():
    with patch("backend.batch.utilities.search.azure_search_handler.LLMHelper") as mock:
        mock_llm_helper = mock.return_value
        yield mock_llm_helper


@pytest.fixture(autouse=True)
def mock_azure_computer_vision_client():
    with patch(
        "backend.batch.utilities.search.azure_search_handler.AzureComputerVisionClient"
    ) as mock:
        azure_computer_vision_client = mock.return_value
        azure_computer_vision_client.vectorize_text.return_value = [3, 2, 1]

        yield azure_computer_vision_client


@pytest.fixture
def handler(env_helper_mock, mock_search_client, mock_llm_helper):
    with patch(
        "backend.batch.utilities.search.azure_search_handler.AzureSearchHelper",
        return_value=mock_search_client,
    ):
        with patch(
            "backend.batch.utilities.search.azure_search_handler.LLMHelper",
            return_value=mock_llm_helper,
        ):
            return AzureSearchHandler(env_helper_mock)


def test_create_search_client(handler, mock_search_client):
    # when
    search_client = handler.create_search_client()

    # then
    assert search_client == mock_search_client


def test_process_results(handler):
    # given
    results = [{"metadata": json.dumps({"chunk": 1}), "content": "Content 1"}]

    # when
    data = handler.process_results(results)

    # then
    assert data[0] == [1, "Content 1"]


def test_process_results_without_chunk(handler):
    # given
    results = [
        {"metadata": "{}", "content": "Content 1"},
        {"metadata": "{}", "content": "Content 2"},
    ]

    # when
    data = handler.process_results(results)

    # then
    assert data == [[0, "Content 1"], [1, "Content 2"]]


def test_process_results_null(handler):
    # given
    results = []

    # when
    data = handler.process_results(results)

    # then
    assert len(data) == 0


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


@patch("backend.batch.utilities.search.azure_search_handler.tiktoken")
def test_query_search_uses_tiktoken_encoder(mock_tiktoken, handler, mock_llm_helper):
    # given
    question = "What is the answer?"

    mock_encoder = MagicMock()
    mock_tiktoken.get_encoding.return_value = mock_encoder
    mock_encoder.encode.return_value = [1, 2, 3]

    # when
    handler.query_search(question)

    # then
    mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
    mock_encoder.encode.assert_called_once_with(question)
    mock_llm_helper.generate_embeddings.assert_called_once_with([1, 2, 3])


def test_query_search_performs_hybrid_search(handler, mock_llm_helper):
    # given
    question = "What is the answer?"

    mock_llm_helper.generate_embeddings.return_value = [1, 2, 3]

    # when
    handler.query_search(question)

    # then
    handler.search_client.search.assert_called_once_with(
        search_text=question,
        vector_queries=[
            VectorizedQuery(
                vector=[1, 2, 3],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                filter=handler.env_helper.AZURE_SEARCH_FILTER,
                fields="content_vector",
            )
        ],
        query_type="simple",
        filter=handler.env_helper.AZURE_SEARCH_FILTER,
        top=handler.env_helper.AZURE_SEARCH_TOP_K,
    )


def test_query_search_performs_semantic_search(
    handler, mock_llm_helper, env_helper_mock
):
    # given
    question = "What is the answer?"

    mock_llm_helper.generate_embeddings.return_value = [1, 2, 3]
    env_helper_mock.AZURE_SEARCH_USE_SEMANTIC_SEARCH = True
    env_helper_mock.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "some-semantic-config"

    # when
    handler.query_search(question)

    # then
    handler.search_client.search.assert_called_once_with(
        search_text=question,
        vector_queries=[
            VectorizedQuery(
                vector=[1, 2, 3],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                fields="content_vector",
            )
        ],
        filter=handler.env_helper.AZURE_SEARCH_FILTER,
        query_type="semantic",
        semantic_configuration_name=handler.env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
        query_caption="extractive",
        query_answer="extractive",
        top=handler.env_helper.AZURE_SEARCH_TOP_K,
    )


def test_query_search_converts_results_to_source_documents(
    handler,
):
    # given
    question = "What is the answer?"

    handler.search_client.search.return_value = [
        {
            "id": 1,
            "content": "content1",
            "title": "title1",
            "source": "source1",
            "chunk": "chunk1",
            "offset": "offset1",
            "page_number": "page_number1",
        },
        {
            "id": 2,
            "content": "content2",
            "title": "title2",
            "source": "source2",
            "chunk": "chunk2",
            "offset": "offset2",
            "page_number": "page_number2",
        },
    ]

    expected_results = [
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

    # when
    actual_results = handler.query_search(question)

    # then
    assert actual_results == expected_results


def test_hybrid_search_with_advanced_image_processing(
    handler: AzureSearchHandler,
    mock_llm_helper: MagicMock,
    mock_azure_computer_vision_client: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.USE_ADVANCED_IMAGE_PROCESSING = True
    mock_llm_helper.generate_embeddings.return_value = [1, 2, 3]

    question = "What is the answer?"

    # when
    handler.query_search(question)

    # then
    mock_azure_computer_vision_client.vectorize_text.assert_called_once_with(question)

    handler.search_client.search.assert_called_once_with(
        search_text=question,
        vector_queries=[
            VectorizedQuery(
                vector=[1, 2, 3],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                filter=handler.env_helper.AZURE_SEARCH_FILTER,
                fields="content_vector",
            ),
            VectorizedQuery(
                vector=[3, 2, 1],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                fields="image_vector",
            ),
        ],
        query_type="simple",
        filter=handler.env_helper.AZURE_SEARCH_FILTER,
        top=handler.env_helper.AZURE_SEARCH_TOP_K,
    )


def test_semantic_search_with_advanced_image_processing(
    handler: AzureSearchHandler,
    mock_llm_helper: MagicMock,
    mock_azure_computer_vision_client: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.USE_ADVANCED_IMAGE_PROCESSING = True
    env_helper_mock.AZURE_SEARCH_USE_SEMANTIC_SEARCH = True
    env_helper_mock.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "some-semantic-config"
    mock_llm_helper.generate_embeddings.return_value = [1, 2, 3]

    question = "What is the answer?"

    # when
    handler.query_search(question)

    # then
    mock_azure_computer_vision_client.vectorize_text.assert_called_once_with(question)

    handler.search_client.search.assert_called_once_with(
        search_text=question,
        vector_queries=[
            VectorizedQuery(
                vector=[1, 2, 3],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                fields="content_vector",
            ),
            VectorizedQuery(
                vector=[3, 2, 1],
                k_nearest_neighbors=handler.env_helper.AZURE_SEARCH_TOP_K,
                fields="image_vector",
            ),
        ],
        filter=handler.env_helper.AZURE_SEARCH_FILTER,
        query_type="semantic",
        semantic_configuration_name=handler.env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
        query_caption="extractive",
        query_answer="extractive",
        top=handler.env_helper.AZURE_SEARCH_TOP_K,
    )
