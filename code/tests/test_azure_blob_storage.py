import pytest
from backend.batch.utilities.helpers.azure_blob_storage_client import (
    AzureBlobStorageClient,
)


@pytest.fixture
def blob_client():
    return AzureBlobStorageClient()


@pytest.mark.azure("This test requires Azure Blob Storage")
def test_upload_and_download_file(blob_client):
    # Upload a file
    file_name = "test_file.txt"
    file_contents = b"Hello, world!"
    blob_client.upload_file(file_contents, file_name)
    # Download the file
    downloaded_contents = blob_client.download_file(file_name)
    # Check that the downloaded contents match the original contents
    assert downloaded_contents == file_contents
    # Delete the file
    blob_client.delete_file(file_name)
