import pytest
from unittest.mock import ANY, MagicMock, patch
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
    blob_client_mock = blob_service_client_mock.get_blob_client.return_value
    blob_client_mock.exists.return_value = exists

    # when
    result = client.file_exists("mock-file")

    # then
    assert result is expected

    blob_service_client_mock.get_blob_client.assert_called_once_with(
        container="mock-container", blob="mock-file"
    )


def test_delete_file(BlobServiceClientMock: MagicMock):
    # given
    client = AzureBlobStorageClient()
    blob_service_client_mock = BlobServiceClientMock.from_connection_string.return_value
    blob_client_mock = blob_service_client_mock.get_blob_client.return_value

    # when
    client.delete_file("mock-file")

    # then
    blob_service_client_mock.get_blob_client.assert_called_once_with(
        container="mock-container", blob="mock-file"
    )
    blob_client_mock.delete_blob.assert_called_once()


def test_upsert_blob_metadata(BlobServiceClientMock: MagicMock):
    # given
    client = AzureBlobStorageClient()
    blob_service_client_mock = BlobServiceClientMock.from_connection_string.return_value
    blob_client_mock = blob_service_client_mock.get_blob_client.return_value
    blob_client_mock.get_blob_properties.return_value.metadata = {
        "other-key": "other-value",
        "old-key": "old-value",
    }

    # when
    client.upsert_blob_metadata(
        "mock-file",
        {
            "old-key": "new-value",
            "new-key": "some-value",
        },
    )

    # then
    blob_service_client_mock.get_blob_client.assert_called_once_with(
        container="mock-container", blob="mock-file"
    )
    blob_client_mock.set_blob_metadata.assert_called_once_with(
        metadata={
            "other-key": "other-value",
            "old-key": "new-value",
            "new-key": "some-value",
        }
    )


@patch("backend.batch.utilities.helpers.AzureBlobStorageHelper.generate_blob_sas")
def test_get_blob_sas(generate_blob_sas_mock: MagicMock):
    # given
    client = AzureBlobStorageClient()
    generate_blob_sas_mock.return_value = "mock-sas"

    # when
    result = client.get_blob_sas("mock-file")

    # then
    assert (
        result
        == "https://mock-account.blob.core.windows.net/mock-container/mock-file?mock-sas"
    )
    generate_blob_sas_mock.assert_called_once_with(
        account_name="mock-account",
        container_name="mock-container",
        blob_name="mock-file",
        user_delegation_key=None,
        account_key="mock-key",
        permission="r",
        expiry=ANY,
    )


@patch("backend.batch.utilities.helpers.AzureBlobStorageHelper.generate_container_sas")
def test_get_container_sas(generate_container_sas_mock: MagicMock):
    # given
    client = AzureBlobStorageClient()
    generate_container_sas_mock.return_value = "mock-sas"

    # when
    result = client.get_container_sas()

    # then
    assert result == "?mock-sas"
    generate_container_sas_mock.assert_called_once_with(
        account_name="mock-account",
        container_name="mock-container",
        user_delegation_key=None,
        account_key="mock-key",
        permission="r",
        expiry=ANY,
    )
