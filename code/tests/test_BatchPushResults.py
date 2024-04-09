from unittest.mock import patch, Mock
from azure.functions import QueueMessage
from backend.batch.BatchPushResults import do_batch_push_results
from backend.batch.BatchPushResults import _get_file_name_from_message


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
def test_do_batch_push_results(
    mock_document_processor, mock_azure_blob_storage_client, mock_config_helper
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

    do_batch_push_results(mock_queue_message)

    mock_document_processor_instance.process.assert_called_once_with(
        source_url="test_blob_sas", processors=[md_processor]
    )
    mock_blob_client_instance.upsert_blob_metadata.assert_called_once_with(
        "test/test/test_filename.md", {"embeddings_added": "true"}
    )
