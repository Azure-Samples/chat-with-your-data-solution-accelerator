import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.AzureBlobStorageHelper import (
    AzureBlobStorageClient,
)


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureBlobStorageHelper.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = "keys"
        env_helper.AZURE_BLOB_ACCOUNT_NAME = "mock-account"
        env_helper.AZURE_BLOB_ACCOUNT_KEY = "mock-key"
        env_helper.AZURE_BLOB_CONTAINER_NAME = "mock-container"

        yield env_helper


@pytest.fixture()
def BlobServiceClientMock():
    with patch(
        "backend.batch.utilities.helpers.AzureBlobStorageHelper.BlobServiceClient"
    ) as mock:
        yield mock


@pytest.mark.parametrize("exists,expected", [(True, True), (False, False)])
def test_file_exists(BlobServiceClientMock: MagicMock, exists: bool, expected: bool):
    # given
    client = AzureBlobStorageClient()
    blob_service_client_mock = BlobServiceClientMock.from_connection_string.return_value
    container_client_mock = blob_service_client_mock.get_container_client.return_value
    blob_client_mock = container_client_mock.get_blob_client.return_value
    blob_client_mock.exists.return_value = exists

    # when
    result = client.file_exists("mock-file")

    # then
    assert result is expected

    blob_service_client_mock.get_container_client.assert_called_once_with(
        "mock-container"
    )
    container_client_mock.get_blob_client.assert_called_once_with("mock-file")
