import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.processors.DocumentProcessorHelper import (
    DocumentProcessor,
)
from backend.batch.utilities.helpers.Processor import Processor

from backend.batch.utilities.helpers.DocumentLoadingHelper import DocumentLoading
from backend.batch.utilities.helpers.DocumentChunkingHelper import DocumentChunking
from backend.batch.utilities.common.SourceDocument import SourceDocument
from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper

AZURE_SEARCH_INDEXER_NAME = "mock-indexer-name"


@pytest.fixture(autouse=True)
def azure_search_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.processors.DocumentProcessorHelper.AzureSearchHelper"
    ) as mock:
        yield mock


def test_process_use_advanced_image_processing_skips_processing(
    azure_search_helper_mock,
):
    # given
    vector_store_mock = MagicMock()
    azure_search_helper_mock.return_value.get_vector_store.return_value = (
        vector_store_mock
    )
    document_processor = DocumentProcessor(None)
    processor = Processor("jpg", None, None, use_advanced_image_processing=True)

    # when
    document_processor.process("some-url", [processor])

    # then
    vector_store_mock.add_documents.assert_not_called()


def test_process_with_non_advanced_image_processing_adds_documents_to_vector_store(
    azure_search_helper_mock,
):
    # given
    vector_store_mock = MagicMock()
    azure_search_helper_mock.return_value.get_vector_store.return_value = (
        vector_store_mock
    )
    document_processor = DocumentProcessor(None)
    processor = Processor("jpg", None, None, use_advanced_image_processing=False)
    source_url = "some-url"
    documents = [
        SourceDocument("1", "document1", "content1"),
        SourceDocument("2", "document2", "content2"),
    ]

    with patch.object(
        DocumentLoading, "load", return_value=documents
    ) as load_mock, patch.object(
        DocumentChunking, "chunk", return_value=documents
    ) as chunk_mock:
        # when
        document_processor.process(source_url, [processor])

        # then
        load_mock.assert_called_once_with(source_url, processor.loading)
        chunk_mock.assert_called_once_with(documents, processor.chunking)


def test_process_file_with_non_url_extension_processes_and_adds_metadata(
    azure_search_helper_mock,
):
    # given
    vector_store_mock = MagicMock()
    azure_search_helper_mock.return_value.get_vector_store.return_value = (
        vector_store_mock
    )
    document_processor = DocumentProcessor(blob_client=MagicMock())
    source_url = "some-url"
    file_name = "file.jpg"

    with patch.object(
        ConfigHelper, "get_active_config_or_default"
    ) as config_mock, patch.object(document_processor, "process") as process_mock:
        # when
        document_processor.process_file(source_url, file_name)

        # then
        config_mock.assert_called_once()
        process_mock.assert_called_once_with(source_url="some-url", processors=[])
