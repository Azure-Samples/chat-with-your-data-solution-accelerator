import pytest
from .azureblobstorage import AzureBlobStorageClient

@pytest.fixture
def blob_client():
    return AzureBlobStorageClient()

def test_upload_and_download_file(blob_client):
    # Upload a file
    file_name = "test_file.txt"
    file_contents = b"Hello, world!"
    blob_url = blob_client.upload_file(file_contents, file_name)

    # Download the file
    downloaded_contents = blob_client.download_file(file_name)

    # Check that the downloaded contents match the original contents
    assert downloaded_contents == file_contents