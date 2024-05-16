import json
import sys
import os
import pytest
from unittest.mock import patch
from azure.functions import QueueMessage


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.batch_push_results import (  # noqa: E402
    batch_push_results,
    _get_file_name_from_message,
)


@pytest.fixture(autouse=True)
def get_processor_handler_mock():
    with patch(
        "backend.batch.batch_push_results.EmbedderFactory.create"
    ) as mock_create_embedder, patch(
        "backend.batch.batch_push_results.Search.get_search_handler"
    ) as mock_get_search_handler:
        processor_handler_create = mock_create_embedder.return_value
        processor_handler_get_search_handler = mock_get_search_handler.return_value
        yield processor_handler_create, processor_handler_get_search_handler


def test_get_file_name_from_message():
    mock_queue_message = QueueMessage(
        body='{"message": "test message", "filename": "test_filename.md"}'
    )
    message_body = json.loads(mock_queue_message.get_body().decode("utf-8"))
    file_name = _get_file_name_from_message(message_body)

    assert file_name == "test_filename.md"


def test_get_file_name_from_message_no_filename():
    mock_queue_message = QueueMessage(
        body='{"data": { "url": "test/test/test_filename.md"} }'
    )
    message_body = json.loads(mock_queue_message.get_body().decode("utf-8"))
    file_name = _get_file_name_from_message(message_body)

    assert file_name == "test_filename.md"


def test_batch_push_results_with_unhandled_event_type():
    mock_queue_message = QueueMessage(
        body='{"eventType": "Microsoft.Storage.BlobUpdated"}'
    )

    with pytest.raises(NotImplementedError):
        batch_push_results.build().get_user_function()(mock_queue_message)


@patch("backend.batch.batch_push_results._process_document_created_event")
def test_batch_push_results_with_blob_created_event(
    mock_process_document_created_event,
):
    mock_queue_message = QueueMessage(
        body='{"eventType": "Microsoft.Storage.BlobCreated", "filename": "test/test/test_filename.md"}'
    )

    batch_push_results.build().get_user_function()(mock_queue_message)

    expected_message_body = json.loads(mock_queue_message.get_body().decode("utf-8"))
    mock_process_document_created_event.assert_called_once_with(expected_message_body)


@patch("backend.batch.batch_push_results._process_document_created_event")
def test_batch_push_results_with_no_event(mock_process_document_created_event):
    mock_queue_message = QueueMessage(
        body='{"data": { "url": "test/test/test_filename.md"} }'
    )

    batch_push_results.build().get_user_function()(mock_queue_message)

    expected_message_body = json.loads(mock_queue_message.get_body().decode("utf-8"))
    mock_process_document_created_event.assert_called_once_with(expected_message_body)


@patch("backend.batch.batch_push_results._process_document_deleted_event")
def test_batch_push_results_with_blob_deleted_event(
    mock_process_document_deleted_event,
):
    mock_queue_message = QueueMessage(
        body='{"eventType": "Microsoft.Storage.BlobDeleted", "filename": "test/test/test_filename.md"}'
    )

    batch_push_results.build().get_user_function()(mock_queue_message)

    expected_message_body = json.loads(mock_queue_message.get_body().decode("utf-8"))
    mock_process_document_deleted_event.assert_called_once_with(expected_message_body)


@patch("backend.batch.batch_push_results.EnvHelper")
@patch("backend.batch.batch_push_results.AzureBlobStorageClient")
def test_batch_push_results_with_blob_created_event_uses_embedder(
    mock_azure_blob_storage_client,
    mock_env_helper,
    get_processor_handler_mock,
):
    mock_create_embedder, mock_get_search_handler = get_processor_handler_mock

    mock_queue_message = QueueMessage(
        body='{"eventType": "Microsoft.Storage.BlobCreated", "filename": "test/test/test_filename.md"}'
    )

    mock_blob_client_instance = mock_azure_blob_storage_client.return_value
    mock_blob_client_instance.get_blob_sas.return_value = "test_blob_sas"

    batch_push_results.build().get_user_function()(mock_queue_message)
    mock_create_embedder.embed_file.assert_called_once_with(
        "test_blob_sas", "test/test/test_filename.md"
    )


@patch("backend.batch.batch_push_results.EnvHelper")
def test_batch_push_results_with_blob_deleted_event_uses_search_to_delete_with_sas_appended(
    mock_env_helper,
    get_processor_handler_mock,
):
    mock_create_embedder, mock_get_search_handler = get_processor_handler_mock

    mock_queue_message = QueueMessage(
        body='{"eventType": "Microsoft.Storage.BlobDeleted", "data": { "url": "https://test.test/test/test_filename.pdf"}}'
    )

    batch_push_results.build().get_user_function()(mock_queue_message)
    mock_get_search_handler.delete_by_source.assert_called_once_with(
        "https://test.test/test/test_filename.pdf_SAS_TOKEN_PLACEHOLDER_"
    )
