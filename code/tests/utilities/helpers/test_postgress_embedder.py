from unittest.mock import MagicMock, patch, call

import pytest
from backend.batch.utilities.helpers.embedders.postgres_embedder import PostgresEmbedder
from backend.batch.utilities.common.source_document import SourceDocument
from backend.batch.utilities.helpers.config.embedding_config import EmbeddingConfig
from backend.batch.utilities.document_loading.strategies import LoadingStrategy
from backend.batch.utilities.document_loading import LoadingSettings
from backend.batch.utilities.document_chunking.chunking_strategy import ChunkingSettings

CHUNKING_SETTINGS = ChunkingSettings({"strategy": "layout", "size": 1, "overlap": 0})
LOADING_SETTINGS = LoadingSettings({"strategy": LoadingStrategy.LAYOUT})


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.postgres_embedder.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = [
            0
        ] * 1536
        mock_completion = llm_helper.get_chat_completion.return_value
        choice = MagicMock()
        choice.message.content = "This is a caption for an image"
        mock_completion.choices = [choice]
        llm_helper.generate_embeddings.return_value = [123]
        yield llm_helper


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.push_embedder.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        yield env_helper


@pytest.fixture(autouse=True)
def azure_postgres_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.postgres_embedder.AzurePostgresHelper"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_config_helper():
    with patch(
        "backend.batch.utilities.helpers.embedders.postgres_embedder.ConfigHelper"
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
        "backend.batch.utilities.helpers.embedders.postgres_embedder.DocumentLoading"
    ) as mock:
        expected_documents = [
            SourceDocument(content="some content", source="some source")
        ]
        mock.return_value.load.return_value = expected_documents
        yield mock


@pytest.fixture(autouse=True)
def document_chunking_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.postgres_embedder.DocumentChunking"
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


def test_embed_file(
    document_chunking_mock,
    document_loading_mock,
    llm_helper_mock,
    azure_postgres_helper_mock,
):
    postgres_embedder = PostgresEmbedder(MagicMock(), MagicMock())
    # Setup test data
    source_url = "https://example.com/document.pdf"
    file_name = "document.pdf"
    file_extension = "pdf"
    embedding_config = MagicMock()
    postgres_embedder.embedding_configs[file_extension] = (
        embedding_config  # This needs to be adapted if `self.embedder` isn't set.
    )

    # Mock methods
    llm_helper_mock.generate_embeddings.return_value = [0.1, 0.2, 0.3]
    azure_postgres_helper_mock.create_vector_store.return_value = True

    # Execute
    postgres_embedder.embed_file(source_url, file_name)

    # Assert method calls
    document_loading_mock.return_value.load.assert_called_once_with(
        source_url, embedding_config.loading
    )
    document_chunking_mock.return_value.chunk.assert_called_once_with(
        document_loading_mock.return_value.load.return_value, embedding_config.chunking
    )
    llm_helper_mock.generate_embeddings.assert_has_calls(
        [call("some content"), call("some other content")]
    )


def test_advanced_image_processing_not_implemented():
    postgres_embedder = PostgresEmbedder(MagicMock(), MagicMock())
    # Test for unsupported advanced image processing
    file_extension = "jpg"
    embedding_config = MagicMock()
    embedding_config.use_advanced_image_processing = True
    postgres_embedder.embedding_configs[file_extension] = embedding_config

    # Mock config method
    postgres_embedder.config.get_advanced_image_processing_image_types = MagicMock(
        return_value=["jpg", "png"]
    )

    # Use pytest.raises to check the exception
    with pytest.raises(NotImplementedError) as context:
        postgres_embedder.embed_file("https://example.com/image.jpg", "image.jpg")

    # Assert that the exception message matches the expected one
    assert (
        str(context.value)
        == "Advanced image processing is not supported in PostgresEmbedder."
    )


def test_postgres_embed_file_loads_documents(document_loading_mock, env_helper_mock):
    # given
    push_embedder = PostgresEmbedder(MagicMock(), env_helper_mock)
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


def test_postgres_embed_file_chunks_documents(
    document_loading_mock, document_chunking_mock, env_helper_mock
):
    # given
    push_embedder = PostgresEmbedder(MagicMock(), env_helper_mock)

    # when
    push_embedder.embed_file(
        "some-url",
        "some-file-name.pdf",
    )

    # then
    document_chunking_mock.return_value.chunk.assert_called_once_with(
        document_loading_mock.return_value.load.return_value, CHUNKING_SETTINGS
    )
