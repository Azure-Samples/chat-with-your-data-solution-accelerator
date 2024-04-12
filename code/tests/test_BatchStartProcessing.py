import sys
import os
from unittest.mock import patch, Mock

sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.BatchStartProcessing import batch_start_processing  # noqa: E402


@patch("backend.batch.BatchStartProcessing.create_queue_client")
@patch("backend.batch.BatchStartProcessing.AzureBlobStorageClient")
def test_batch_start_processing_processes_all(
    mock_blob_storage_client, mock_create_queue_client
):
    mock_http_request = Mock()
    mock_http_request.params = dict()
    mock_http_request.params["process_all"] = "true"

    mock_queue_client = Mock()
    mock_create_queue_client.return_value = mock_queue_client

    mock_blob_storage_client.return_value.get_all_files.return_value = [
        {"filename": "file_name_one", "embeddings_added": False}
    ]

    response = batch_start_processing.build().get_user_function()(mock_http_request)

    assert response.status_code == 200

    mock_queue_client.send_message.assert_called_once_with(
        b'{"filename": "file_name_one"}',
    )


@patch("backend.batch.BatchStartProcessing.create_queue_client")
@patch("backend.batch.BatchStartProcessing.AzureBlobStorageClient")
def test_batch_start_processing_filters_filter_no_embeddings(
    mock_blob_storage_client, mock_create_queue_client
):
    mock_http_request = Mock()
    mock_http_request.params = dict()
    mock_http_request.params["process_all"] = "false"

    mock_queue_client = Mock()
    mock_create_queue_client.return_value = mock_queue_client

    mock_blob_storage_client.return_value.get_all_files.return_value = [
        {
            "filename": "file_name_one",
            "embeddings_added": True,  # will get filtered out
        },
        {"filename": "file_name_two", "embeddings_added": False},
    ]
    response = batch_start_processing.build().get_user_function()(mock_http_request)

    assert response.status_code == 200

    mock_queue_client.send_message.assert_called_once_with(
        b'{"filename": "file_name_two"}',
    )
