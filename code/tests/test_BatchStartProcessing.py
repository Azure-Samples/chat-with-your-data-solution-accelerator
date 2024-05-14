import sys
import os
import pytest
from unittest.mock import call, patch, Mock

sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.BatchStartProcessing import batch_start_processing  # noqa: E402


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.BatchStartProcessing.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_SEARCH_INDEXER_NAME = "AZURE_SEARCH_INDEXER_NAME"

        yield env_helper


@pytest.fixture(autouse=True)
def mock_integrated_vectorization_embedder():
    with patch(
        "backend.batch.BatchStartProcessing.IntegratedVectorizationEmbedder"
    ) as mock:
        yield mock


@patch("backend.batch.BatchStartProcessing.create_queue_client")
@patch("backend.batch.BatchStartProcessing.AzureBlobStorageClient")
def test_batch_start_processing_processes_all(
    mock_blob_storage_client, mock_create_queue_client, env_helper_mock
):
    # given
    mock_http_request = Mock()
    mock_http_request.params = dict()

    mock_queue_client = Mock()
    mock_create_queue_client.return_value = mock_queue_client
    mock_blob_storage_client.return_value.get_all_files.return_value = [
        {"filename": "file_name_one", "embeddings_added": False},
        {"filename": "file_name_two", "embeddings_added": True},
    ]
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = False
    # when
    response = batch_start_processing.build().get_user_function()(mock_http_request)

    # then
    assert response.status_code == 200
    assert response.get_body() == b"Conversion started successfully for 2 documents."

    send_message_calls = mock_queue_client.send_message.call_args_list
    assert len(send_message_calls) == 2
    assert send_message_calls[0] == call(b'{"filename": "file_name_one"}')
    assert send_message_calls[1] == call(b'{"filename": "file_name_two"}')


@patch("backend.batch.BatchStartProcessing.create_queue_client")
@patch("backend.batch.BatchStartProcessing.AzureBlobStorageClient")
def test_batch_start_processing_processes_all_integrated_vectorization(
    mock_blob_storage_client,
    mock_create_queue_client,
    mock_integrated_vectorization_embedder,
    env_helper_mock,
):
    # given
    mock_http_request = Mock()
    mock_http_request.params = dict()

    mock_queue_client = Mock()
    mock_create_queue_client.return_value = mock_queue_client
    mock_blob_storage_client.return_value.get_all_files.return_value = [
        {"filename": "file_name_one", "embeddings_added": False},
        {"filename": "file_name_two", "embeddings_added": True},
    ]
    mock_integrated_vectorization_embedder.return_value.reprocess_all.return_value = (
        None
    )
    env_helper_mock.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True

    # when
    response = batch_start_processing.build().get_user_function()(mock_http_request)

    # then
    assert response.status_code == 200
    assert response.get_body() == b"Conversion started successfully for 2 documents."

    send_message_calls = mock_queue_client.send_message.call_args_list
    assert len(send_message_calls) == 0
    mock_integrated_vectorization_embedder.return_value.reprocess_all.assert_called_once()
