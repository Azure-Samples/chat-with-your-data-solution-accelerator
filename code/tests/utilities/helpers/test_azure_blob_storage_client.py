"""
Unit tests for azure_blob_storage_client.py module.
Tests focus on actual business logic: file operations, SAS generation, metadata management,
and authentication modes (key-based vs RBAC).
"""

from unittest.mock import Mock, patch

import pytest

from backend.batch.utilities.helpers.azure_blob_storage_client import (
    AzureBlobStorageClient,
    connection_string,
    create_queue_client,
)


@pytest.fixture(autouse=True)
def mock_env_helper():
    """Mock EnvHelper with key-based auth configuration."""
    with patch("backend.batch.utilities.helpers.azure_blob_storage_client.EnvHelper") as mock:
        env = Mock()
        env.AZURE_AUTH_TYPE = "keys"
        env.AZURE_BLOB_ACCOUNT_NAME = "teststorageaccount"
        env.AZURE_BLOB_ACCOUNT_KEY = "dGVzdC1hY2NvdW50LWtleQ=="
        env.AZURE_BLOB_CONTAINER_NAME = "test-container"
        env.AZURE_STORAGE_ACCOUNT_ENDPOINT = "https://teststorageaccount.blob.core.windows.net/"
        env.DOCUMENT_PROCESSING_QUEUE_NAME = "test-queue"
        env.MANAGED_IDENTITY_CLIENT_ID = None
        mock.return_value = env
        yield env


@pytest.fixture
def mock_env_helper_rbac():
    """Mock EnvHelper with RBAC auth configuration."""
    with patch("backend.batch.utilities.helpers.azure_blob_storage_client.EnvHelper") as mock:
        env = Mock()
        env.AZURE_AUTH_TYPE = "rbac"
        env.AZURE_BLOB_ACCOUNT_NAME = "teststorageaccount"
        env.AZURE_BLOB_CONTAINER_NAME = "test-container"
        env.AZURE_STORAGE_ACCOUNT_ENDPOINT = "https://teststorageaccount.blob.core.windows.net/"
        env.DOCUMENT_PROCESSING_QUEUE_NAME = "test-queue"
        env.MANAGED_IDENTITY_CLIENT_ID = "test-client-id"
        mock.return_value = env
        yield env


class TestConnectionString:
    """Tests for connection_string utility function."""

    def test_connection_string_format(self):
        """Test that connection string is correctly formatted."""
        account_name = "myaccount"
        account_key = "mykey123"

        result = connection_string(account_name, account_key)

        assert result == "DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey123;EndpointSuffix=core.windows.net"
        assert "DefaultEndpointsProtocol=https" in result
        assert f"AccountName={account_name}" in result
        assert f"AccountKey={account_key}" in result


class TestCreateQueueClient:
    """Tests for create_queue_client factory function."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.QueueClient")
    def test_create_queue_client_with_key_auth(self, mock_queue_client_class, mock_env_helper):
        """Test queue client creation with key-based authentication."""
        create_queue_client()

        mock_queue_client_class.from_connection_string.assert_called_once()
        call_kwargs = mock_queue_client_class.from_connection_string.call_args[1]
        assert call_kwargs['queue_name'] == "test-queue"
        assert "AccountName=teststorageaccount" in call_kwargs['conn_str']

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.get_azure_credential")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.QueueClient")
    def test_create_queue_client_with_rbac(self, mock_queue_client_class, mock_get_credential, mock_env_helper_rbac):
        """Test queue client creation with RBAC authentication."""
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential

        create_queue_client()

        mock_get_credential.assert_called_once_with("test-client-id")
        mock_queue_client_class.assert_called_once()
        call_kwargs = mock_queue_client_class.call_args[1]
        assert call_kwargs['queue_name'] == "test-queue"
        assert call_kwargs['credential'] == mock_credential
        assert "teststorageaccount.queue.core.windows.net" in call_kwargs['account_url']


class TestAzureBlobStorageClientInitialization:
    """Tests for client initialization with different auth types."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_initialization_with_key_auth(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test client initializes correctly with key-based authentication."""
        client = AzureBlobStorageClient()

        assert client.auth_type == "keys"
        assert client.account_name == "teststorageaccount"
        assert client.account_key == "dGVzdC1hY2NvdW50LWtleQ=="
        assert client.container_name == "test-container"
        assert client.user_delegation_key is None

        mock_credential_class.assert_called_once_with(
            name="teststorageaccount",
            key="dGVzdC1hY2NvdW50LWtleQ=="
        )
        mock_blob_service_class.assert_called_once()

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.get_azure_credential")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    def test_initialization_with_rbac(self, mock_blob_service_class, mock_get_credential, mock_env_helper_rbac):
        """Test client initializes correctly with RBAC authentication."""
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential

        # Mock user delegation key request
        mock_blob_service = Mock()
        mock_user_delegation_key = Mock()
        mock_blob_service.get_user_delegation_key.return_value = mock_user_delegation_key
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()

        assert client.auth_type == "rbac"
        assert client.account_name == "teststorageaccount"
        assert client.account_key is None
        assert client.user_delegation_key == mock_user_delegation_key

        mock_get_credential.assert_called_once_with("test-client-id")
        mock_blob_service.get_user_delegation_key.assert_called_once()

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_initialization_with_custom_parameters(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test client accepts custom account name and container name."""
        client = AzureBlobStorageClient(
            account_name="custom-account",
            account_key="custom-key",
            container_name="custom-container"
        )

        assert client.account_name == "custom-account"
        assert client.account_key == "custom-key"
        assert client.container_name == "custom-container"


class TestFileExistsAndDelete:
    """Tests for file existence check and deletion logic."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_file_exists_returns_true(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test file_exists returns True when blob exists."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = True

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        result = client.file_exists("test-file.pdf")

        assert result is True
        mock_blob_service.get_blob_client.assert_called_once_with(
            container="test-container",
            blob="test-file.pdf"
        )

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_file_exists_returns_false(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test file_exists returns False when blob doesn't exist."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        result = client.file_exists("nonexistent.pdf")

        assert result is False

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_delete_file_when_exists(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test delete_file deletes blob when it exists."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = True

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        client.delete_file("test-file.pdf")

        mock_blob_client.delete_blob.assert_called_once()

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_delete_file_when_not_exists(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test delete_file skips deletion when blob doesn't exist."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        client.delete_file("nonexistent.pdf")

        mock_blob_client.delete_blob.assert_not_called()


class TestDeleteFiles:
    """Tests for batch file deletion logic."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_delete_files_with_integrated_vectorization(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test delete_files with integrated vectorization uses full filename."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = True

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        files = {
            "folder/subfolder/file1.pdf": ["id1"],
            "folder/file2.txt": ["id2"]
        }

        client.delete_files(files, integrated_vectorization=True)

        # Should call get_blob_client with full paths
        assert mock_blob_service.get_blob_client.call_count == 2
        mock_blob_service.get_blob_client.assert_any_call(
            container="test-container",
            blob="folder/subfolder/file1.pdf"
        )
        mock_blob_service.get_blob_client.assert_any_call(
            container="test-container",
            blob="folder/file2.txt"
        )

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_delete_files_without_integrated_vectorization(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test delete_files without integrated vectorization extracts filename only."""
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = True

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        files = {
            "folder/subfolder/file1.pdf": ["id1"],
            "folder/file2.txt": ["id2"]
        }

        client.delete_files(files, integrated_vectorization=False)

        # Should extract filename from path
        mock_blob_service.get_blob_client.assert_any_call(
            container="test-container",
            blob="file1.pdf"
        )
        mock_blob_service.get_blob_client.assert_any_call(
            container="test-container",
            blob="file2.txt"
        )


class TestUploadFile:
    """Tests for file upload with content type detection and SAS generation."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_blob_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_upload_file_with_explicit_content_type(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test upload_file uses provided content type."""
        mock_blob_client = Mock()
        mock_blob_client.url = "https://teststorageaccount.blob.core.windows.net/test-container/test.pdf"

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=test"

        client = AzureBlobStorageClient()
        file_data = b"PDF content here"

        result = client.upload_file(
            file_data,
            "test.pdf",
            content_type="application/pdf",
            metadata={"source": "upload"}
        )

        # Verify upload was called with correct content settings
        upload_call = mock_blob_client.upload_blob.call_args
        assert upload_call[1]['content_settings'].content_type == "application/pdf"
        assert upload_call[1]['metadata'] == {"source": "upload"}
        assert upload_call[1]['overwrite'] is True

        # Verify SAS URL is returned
        assert "sv=2021-06-08" in result
        assert mock_blob_client.url in result

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.chardet")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_blob_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_upload_file_auto_detects_text_content_type(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_chardet, mock_env_helper):
        """Test upload_file auto-detects content type and charset for text files."""
        mock_blob_client = Mock()
        mock_blob_client.url = "https://teststorageaccount.blob.core.windows.net/test-container/test.txt"

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=test"
        mock_chardet.detect.return_value = {"encoding": "utf-8"}

        client = AzureBlobStorageClient()
        file_data = b"Text file content"

        client.upload_file(file_data, "test.txt")

        # Verify charset is added for text files
        upload_call = mock_blob_client.upload_blob.call_args
        content_type = upload_call[1]['content_settings'].content_type
        assert "text/plain" in content_type
        assert "charset=utf-8" in content_type

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_blob_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_upload_file_generates_sas_with_key(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test upload_file generates SAS token using account key."""
        mock_blob_client = Mock()
        mock_blob_client.url = "https://teststorageaccount.blob.core.windows.net/test-container/test.pdf"

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=test"

        client = AzureBlobStorageClient()
        client.upload_file(b"data", "test.pdf", content_type="application/pdf")

        # Verify SAS generation uses account key
        mock_sas.assert_called_once()
        sas_call_kwargs = mock_sas.call_args[1]
        assert sas_call_kwargs['account_key'] == "dGVzdC1hY2NvdW50LWtleQ=="
        assert sas_call_kwargs['user_delegation_key'] is None
        assert sas_call_kwargs['permission'] == "r"


class TestDownloadFile:
    """Tests for file download logic."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_download_file_returns_content(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test download_file returns blob content."""
        mock_download = Mock()
        mock_download.readall.return_value = b"File content data"

        mock_blob_client = Mock()
        mock_blob_client.download_blob.return_value = mock_download

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        result = client.download_file("test-file.pdf")

        assert result == b"File content data"
        mock_blob_service.get_blob_client.assert_called_once_with(
            container="test-container",
            blob="test-file.pdf"
        )


class TestGetAllFiles:
    """Tests for listing all files with metadata and SAS URLs."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_get_all_files_returns_file_list(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test get_all_files returns list of files with metadata."""
        # Create mock blobs
        mock_blob1 = Mock()
        mock_blob1.name = "document.pdf"
        mock_blob1.metadata = {
            "converted": "true",
            "embeddings_added": "false",
            "converted_filename": "converted/document.pdf"
        }

        mock_blob2 = Mock()
        mock_blob2.name = "image.jpg"
        mock_blob2.metadata = None

        mock_blob3 = Mock()
        mock_blob3.name = "converted/document.pdf"
        mock_blob3.metadata = {}

        mock_container_client = Mock()
        mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

        mock_blob_service = Mock()
        mock_blob_service.get_container_client.return_value = mock_container_client
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=container"

        client = AzureBlobStorageClient()
        result = client.get_all_files()

        assert len(result) == 2  # Only non-converted files
        assert result[0]['filename'] == "document.pdf"
        assert result[0]['converted'] is True
        assert result[0]['embeddings_added'] is False
        assert "document.pdf" in result[0]['fullpath']
        assert result[0]['converted_path'] != ""  # Has converted file

        assert result[1]['filename'] == "image.jpg"
        assert result[1]['converted'] is False
        assert result[1]['embeddings_added'] is False

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_get_all_files_handles_missing_metadata(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test get_all_files handles blobs without metadata gracefully."""
        mock_blob = Mock()
        mock_blob.name = "no-metadata.pdf"
        mock_blob.metadata = None

        mock_container_client = Mock()
        mock_container_client.list_blobs.return_value = [mock_blob]

        mock_blob_service = Mock()
        mock_blob_service.get_container_client.return_value = mock_container_client
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=test"

        client = AzureBlobStorageClient()
        result = client.get_all_files()

        assert len(result) == 1
        assert result[0]['converted'] is False
        assert result[0]['embeddings_added'] is False
        assert result[0]['converted_path'] == ""


class TestMetadataOperations:
    """Tests for blob metadata management."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_upsert_blob_metadata_merges_with_existing(self, mock_credential_class, mock_blob_service_class, mock_env_helper):
        """Test upsert_blob_metadata merges new metadata with existing."""
        mock_properties = Mock()
        mock_properties.metadata = {"existing_key": "existing_value", "to_update": "old_value"}

        mock_blob_client = Mock()
        mock_blob_client.get_blob_properties.return_value = mock_properties

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_class.return_value = mock_blob_service

        client = AzureBlobStorageClient()
        client.upsert_blob_metadata(
            "test-file.pdf",
            {"to_update": "new_value", "new_key": "new_value"}
        )

        # Verify metadata was merged and updated
        set_metadata_call = mock_blob_client.set_blob_metadata.call_args[1]
        updated_metadata = set_metadata_call['metadata']

        assert updated_metadata['existing_key'] == "existing_value"
        assert updated_metadata['to_update'] == "new_value"
        assert updated_metadata['new_key'] == "new_value"


class TestSASGeneration:
    """Tests for SAS token generation methods."""

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_get_container_sas_uses_account_key(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test get_container_sas generates SAS with account key."""
        mock_sas.return_value = "sv=2021-06-08&sig=container"
        mock_blob_service_class.return_value = Mock()

        client = AzureBlobStorageClient()
        result = client.get_container_sas()

        assert result == "?sv=2021-06-08&sig=container"

        # Verify SAS generation parameters
        sas_call_kwargs = mock_sas.call_args[1]
        assert sas_call_kwargs['account_name'] == "teststorageaccount"
        assert sas_call_kwargs['container_name'] == "test-container"
        assert sas_call_kwargs['account_key'] == "dGVzdC1hY2NvdW50LWtleQ=="
        assert sas_call_kwargs['user_delegation_key'] is None
        assert sas_call_kwargs['permission'] == "r"

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_blob_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.AzureNamedKeyCredential")
    def test_get_blob_sas_returns_full_url(self, mock_credential_class, mock_blob_service_class, mock_sas, mock_env_helper):
        """Test get_blob_sas returns full URL with SAS token."""
        mock_sas.return_value = "sv=2021-06-08&sig=blob"
        mock_blob_service_class.return_value = Mock()

        client = AzureBlobStorageClient()
        result = client.get_blob_sas("documents/file.pdf")

        expected_url = "https://teststorageaccount.blob.core.windows.net/test-container/documents/file.pdf?sv=2021-06-08&sig=blob"
        assert result == expected_url

        # Verify blob-specific SAS parameters
        sas_call_kwargs = mock_sas.call_args[1]
        assert sas_call_kwargs['blob_name'] == "documents/file.pdf"
        assert sas_call_kwargs['permission'] == "r"

    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.get_azure_credential")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.generate_container_sas")
    @patch("backend.batch.utilities.helpers.azure_blob_storage_client.BlobServiceClient")
    def test_get_container_sas_uses_delegation_key_with_rbac(self, mock_blob_service_class, mock_sas, mock_get_credential, mock_env_helper_rbac):
        """Test get_container_sas uses user delegation key with RBAC."""
        mock_user_delegation_key = Mock()
        mock_blob_service = Mock()
        mock_blob_service.get_user_delegation_key.return_value = mock_user_delegation_key
        mock_blob_service_class.return_value = mock_blob_service

        mock_sas.return_value = "sv=2021-06-08&sig=container"

        client = AzureBlobStorageClient()
        client.get_container_sas()

        # Verify SAS uses delegation key instead of account key
        sas_call_kwargs = mock_sas.call_args[1]
        assert sas_call_kwargs['user_delegation_key'] == mock_user_delegation_key
        assert sas_call_kwargs['account_key'] is None
