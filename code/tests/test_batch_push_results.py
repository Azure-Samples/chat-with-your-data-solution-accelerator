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
    with patch("backend.batch.batch_push_results.EmbedderFactory.create") as mock:
        processor_handler = mock.return_value
        yield processor_handler


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


@patch("backend.batch.batch_push_results.EnvHelper")
@patch("backend.batch.batch_push_results.AzureBlobStorageClient")
def test_batch_push_results(
    mock_azure_blob_storage_client, mock_env_helper, get_processor_handler_mock
):
    mock_queue_message = QueueMessage(
        body='{"message": "test message", "filename": "test/test/test_filename.md"}'
    )

    mock_blob_client_instance = mock_azure_blob_storage_client.return_value
    mock_blob_client_instance.get_blob_sas.return_value = "test_blob_sas"

    batch_push_results.build().get_user_function()(mock_queue_message)
    get_processor_handler_mock.embed_file.assert_called_once_with(
        "test_blob_sas", "test/test/test_filename.md"
    )
