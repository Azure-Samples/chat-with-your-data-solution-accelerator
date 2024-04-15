import sys
import os
from unittest.mock import patch, Mock
from azure.functions import QueueMessage


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.BatchPushResults import (  # noqa: E402
    batch_push_results,
    _get_file_name_from_message,
)


def test_get_file_name_from_message():
    mock_queue_message = QueueMessage(
        body='{"message": "test message", "filename": "test_filename.md"}'
    )

    file_name = _get_file_name_from_message(mock_queue_message)

    assert file_name == "test_filename.md"


def test_get_file_name_from_message_no_filename():
    mock_queue_message = QueueMessage(
        body='{"data": { "url": "test/test/test_filename.md"} }'
    )

    file_name = _get_file_name_from_message(mock_queue_message)

    assert file_name == "test_filename.md"


@patch("backend.batch.BatchPushResults.ConfigHelper")
@patch("backend.batch.BatchPushResults.AzureBlobStorageClient")
@patch("backend.batch.BatchPushResults.DocumentProcessor")
def test_batch_push_results(
    mock_document_processor,
    mock_azure_blob_storage_client,
    mock_config_helper,
):
    mock_queue_message = QueueMessage(
        body='{"message": "test message", "filename": "test/test/test_filename.md"}'
    )

    mock_blob_client_instance = mock_azure_blob_storage_client.return_value
    mock_blob_client_instance.get_blob_sas.return_value = "test_blob_sas"

    mock_document_processor_instance = mock_document_processor.return_value

    md_processor = Mock()
    md_processor.document_type.lower.return_value = "md"
    txt_processor = Mock()
    txt_processor.document_type.lower.return_value = "txt"
    mock_processors = [md_processor, txt_processor]
    mock_config_helper.get_active_config_or_default.return_value.document_processors = (
        mock_processors
    )

    batch_push_results.build().get_user_function()(mock_queue_message)

    mock_document_processor_instance.process.assert_called_once_with(
        source_url="test_blob_sas", processors=[md_processor]
    )
    mock_blob_client_instance.upsert_blob_metadata.assert_called_once_with(
        "test/test/test_filename.md", {"embeddings_added": "true"}
    )
