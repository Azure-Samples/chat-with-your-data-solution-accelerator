import json
import pytest
from unittest.mock import MagicMock, call, patch
from backend.batch.utilities.helpers.embedders.push_embedder import PushEmbedder
from backend.batch.utilities.document_chunking.chunking_strategy import ChunkingSettings
from backend.batch.utilities.document_loading import LoadingSettings
from backend.batch.utilities.document_loading.strategies import LoadingStrategy
from backend.batch.utilities.common.source_document import SourceDocument
from backend.batch.utilities.helpers.config.embedding_config import EmbeddingConfig

CHUNKING_SETTINGS = ChunkingSettings({"strategy": "layout", "size": 1, "overlap": 0})
LOADING_SETTINGS = LoadingSettings({"strategy": LoadingStrategy.LAYOUT})


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = [
            0
        ] * 1536
        llm_helper.generate_embeddings.return_value = [123]
        yield mock


@pytest.fixture(autouse=True)
def azure_search_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.AzureSearchHelper"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_config_helper():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.ConfigHelper"
    ) as mock:
        config_helper = mock.get_active_config_or_default.return_value
        config_helper.document_processors = [
            EmbeddingConfig(
                "jpg",
                CHUNKING_SETTINGS,
                LOADING_SETTINGS,
                use_advanced_image_processing=True,
            ),
            EmbeddingConfig(
                "pdf",
                CHUNKING_SETTINGS,
                LOADING_SETTINGS,
                use_advanced_image_processing=False,
            ),
        ]
        config_helper.get_advanced_image_processing_image_types.return_value = {
            "jpeg",
            "jpg",
            "png",
        }
        yield config_helper


@pytest.fixture(autouse=True)
def document_loading_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.DocumentLoading"
    ) as mock:
        expected_documents = [
            SourceDocument(content="some content", source="some source")
        ]
        mock.return_value.load.return_value = expected_documents
        yield mock


@pytest.fixture(autouse=True)
def document_chunking_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.DocumentChunking"
    ) as mock:
        expected_chunked_documents = [
            SourceDocument(
                content="some content",
                source="some source",
                id="some id",
                title="some-title",
                offset=1,
                chunk=1,
                page_number=1,
                chunk_id="some chunk id",
            ),
            SourceDocument(
                content="some other content",
                source="some other source",
                id="some other id",
                title="some other-title",
                offset=2,
                chunk=2,
                page_number=2,
                chunk_id="some other chunk id",
            ),
        ]
        mock.return_value.chunk.return_value = expected_chunked_documents
        yield mock


@pytest.fixture(autouse=True)
def azure_computer_vision_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.AzureComputerVisionClient"
    ) as mock:
        yield mock


def test_embed_file_advanced_image_processing_skips_document_processing(
    azure_search_helper_mock,
):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())

    # when
    push_embedder.embed_file("some-url", "some-file-name.jpg")

    # then
    azure_search_helper_mock.return_value.get_search_client.assert_not_called()


def test_embed_file_advanced_image_processing_vectorizes_image(
    azure_computer_vision_mock,
):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())
    source_url = "http://localhost:8080/some-file-name.jpg"

    # when
    push_embedder.embed_file(source_url, "some-file-name.jpg")

    # then
    azure_computer_vision_mock.return_value.vectorize_image.assert_called_once_with(
        source_url
    )


def test_embed_file_use_advanced_image_processing_does_not_vectorize_image_if_unsupported(
    azure_computer_vision_mock, mock_config_helper, azure_search_helper_mock
):
    # given
    mock_config_helper.document_processors = [
        EmbeddingConfig(
            "txt",
            CHUNKING_SETTINGS,
            LOADING_SETTINGS,
            use_advanced_image_processing=True,
        ),
    ]

    push_embedder = PushEmbedder(MagicMock(), MagicMock())
    source_url = "http://localhost:8080/some-file-name.txt"

    # when
    push_embedder.embed_file(source_url, "some-file-name.txt")

    # then
    azure_computer_vision_mock.return_value.vectorize_image.assert_not_called()
    azure_search_helper_mock.return_value.get_search_client.assert_called_once()


def test_embed_file_loads_documents(document_loading_mock):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())
    source_url = "some-url"

    # when
    push_embedder.embed_file(
        source_url,
        "some-file-name.pdf",
    )

    # then
    document_loading_mock.return_value.load.assert_called_once_with(
        source_url, LOADING_SETTINGS
    )


def test_embed_file_chunks_documents(document_loading_mock, document_chunking_mock):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())

    # when
    push_embedder.embed_file(
        "some-url",
        "some-file-name.pdf",
    )

    # then
    document_chunking_mock.return_value.chunk.assert_called_once_with(
        document_loading_mock.return_value.load.return_value, CHUNKING_SETTINGS
    )


def test_embed_file_generates_embeddings_for_documents(llm_helper_mock):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())

    # when
    push_embedder.embed_file(
        "some-url",
        "some-file-name.pdf",
    )

    # then
    llm_helper_mock.return_value.generate_embeddings.assert_has_calls(
        [call("some content"), call("some other content")]
    )


def test_embed_file_stores_documents_in_search_index(
    document_chunking_mock,
    llm_helper_mock,
    azure_search_helper_mock,
):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())

    # when
    push_embedder.embed_file(
        "some-url",
        "some-file-name.pdf",
    )

    # then
    expected_chunked_documents = document_chunking_mock.return_value.chunk.return_value
    azure_search_helper_mock.return_value.get_search_client.return_value.upload_documents.assert_called_once_with(
        [
            {
                "id": expected_chunked_documents[0].id,
                "content": expected_chunked_documents[0].content,
                "content_vector": llm_helper_mock.return_value.generate_embeddings.return_value,
                "metadata": json.dumps(
                    {
                        "id": expected_chunked_documents[0].id,
                        "source": expected_chunked_documents[0].source,
                        "title": expected_chunked_documents[0].title,
                        "chunk": expected_chunked_documents[0].chunk,
                        "offset": expected_chunked_documents[0].offset,
                        "page_number": expected_chunked_documents[0].page_number,
                        "chunk_id": expected_chunked_documents[0].chunk_id,
                    }
                ),
                "title": expected_chunked_documents[0].title,
                "source": expected_chunked_documents[0].source,
                "chunk": expected_chunked_documents[0].chunk,
                "offset": expected_chunked_documents[0].offset,
            },
            {
                "id": expected_chunked_documents[1].id,
                "content": expected_chunked_documents[1].content,
                "content_vector": llm_helper_mock.return_value.generate_embeddings.return_value,
                "metadata": json.dumps(
                    {
                        "id": expected_chunked_documents[1].id,
                        "source": expected_chunked_documents[1].source,
                        "title": expected_chunked_documents[1].title,
                        "chunk": expected_chunked_documents[1].chunk,
                        "offset": expected_chunked_documents[1].offset,
                        "page_number": expected_chunked_documents[1].page_number,
                        "chunk_id": expected_chunked_documents[1].chunk_id,
                    }
                ),
                "title": expected_chunked_documents[1].title,
                "source": expected_chunked_documents[1].source,
                "chunk": expected_chunked_documents[1].chunk,
                "offset": expected_chunked_documents[1].offset,
            },
        ]
    )


def test_embed_file_raises_exception_on_failure(
    azure_search_helper_mock,
):
    # given
    push_embedder = PushEmbedder(MagicMock(), MagicMock())

    successful_indexing_result = MagicMock()
    successful_indexing_result.succeeded = True
    failed_indexing_result = MagicMock()
    failed_indexing_result.succeeded = False
    azure_search_helper_mock.return_value.get_search_client.return_value.upload_documents.return_value = [
        successful_indexing_result,
        failed_indexing_result,
    ]

    # when + then
    with pytest.raises(Exception):
        push_embedder.embed_file(
            "some-url",
            "some-file-name.pdf",
        )
