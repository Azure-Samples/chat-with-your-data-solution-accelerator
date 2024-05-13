import mimetypes
from typing import Optional
from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    generate_container_sas,
    ContentSettings,
    UserDelegationKey,
)
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy
import chardet
from .env_helper import EnvHelper
from azure.identity import DefaultAzureCredential


def connection_string(account_name: str, account_key: str):
    return f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"


def create_queue_client():
    env_helper: EnvHelper = EnvHelper()
    if env_helper.AZURE_AUTH_TYPE == "rbac":
        return QueueClient(
            account_url=f"https://{env_helper.AZURE_BLOB_ACCOUNT_NAME}.queue.core.windows.net/",
            queue_name=env_helper.DOCUMENT_PROCESSING_QUEUE_NAME,
            credential=DefaultAzureCredential(),
            message_encode_policy=BinaryBase64EncodePolicy(),
        )

    else:
        return QueueClient.from_connection_string(
            conn_str=connection_string(
                env_helper.AZURE_BLOB_ACCOUNT_NAME, env_helper.AZURE_BLOB_ACCOUNT_KEY
            ),
            queue_name=env_helper.DOCUMENT_PROCESSING_QUEUE_NAME,
            message_encode_policy=BinaryBase64EncodePolicy(),
        )


class AzureBlobStorageClient:
    def __init__(
        self,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        container_name: Optional[str] = None,
    ):
        env_helper: EnvHelper = EnvHelper()

        self.auth_type = env_helper.AZURE_AUTH_TYPE
        if self.auth_type == "rbac":
            self.account_name = (
                account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
            )
            self.account_key = None
            self.container_name: str = (
                container_name
                if container_name
                else env_helper.AZURE_BLOB_CONTAINER_NAME
            )
            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{self.account_name}.blob.core.windows.net/",
                credential=DefaultAzureCredential(),
            )
            self.user_delegation_key = self.request_user_delegation_key(
                blob_service_client=self.blob_service_client
            )
        else:
            self.account_name = (
                account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
            )
            self.account_key = (
                account_key if account_key else env_helper.AZURE_BLOB_ACCOUNT_KEY
            )
            self.connect_str = connection_string(self.account_name, self.account_key)
            self.container_name: str = (
                container_name
                if container_name
                else env_helper.AZURE_BLOB_CONTAINER_NAME
            )
            self.blob_service_client: BlobServiceClient = (
                BlobServiceClient.from_connection_string(self.connect_str)
            )
            self.user_delegation_key = None

    def request_user_delegation_key(
        self, blob_service_client: BlobServiceClient
    ) -> UserDelegationKey:
        # Get a user delegation key that's valid for 1 day
        delegation_key_start_time = datetime.utcnow()
        delegation_key_expiry_time = delegation_key_start_time + timedelta(days=1)

        user_delegation_key = blob_service_client.get_user_delegation_key(
            key_start_time=delegation_key_start_time,
            key_expiry_time=delegation_key_expiry_time,
        )
        return user_delegation_key

    def file_exists(self, file_name):
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )

        return blob_client.exists()

    def upload_file(
        self,
        bytes_data,
        file_name,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ):
        # Create a blob client using the local file name as the name for the blob
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )

        content_settings = ContentSettings(content_type=content_type)

        if content_type is None:
            content_type = mimetypes.MimeTypes().guess_type(file_name)[0]
            charset = (
                f"; charset={chardet.detect(bytes_data)['encoding']}"
                if content_type == "text/plain"
                else ""
            )
            content_type = content_type if content_type is not None else "text/plain"
            content_settings = ContentSettings(content_type=content_type + charset)

        # Upload the created file
        blob_client.upload_blob(
            bytes_data,
            overwrite=True,
            content_settings=content_settings,
            metadata=metadata,
        )
        # Generate a SAS URL to the blob and return it, if auth_type is rbac, account_key is None, if not, user_delegation_key is None.
        return (
            blob_client.url
            + "?"
            + generate_blob_sas(
                self.account_name,
                self.container_name,
                file_name,
                user_delegation_key=self.user_delegation_key,
                account_key=self.account_key,
                permission="r",
                expiry=datetime.utcnow() + timedelta(hours=3),
            )
        )

    def download_file(self, file_name):
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )
        return blob_client.download_blob().readall()

    def delete_file(self, file_name):
        """
        Deletes a file from the Azure Blob Storage container.

        Args:
            file_name (str): The name of the file to delete.

        Returns:
            None
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )
        blob_client.delete_blob()

    def get_all_files(self):
        # Get all files in the container from Azure Blob Storage
        container_client = self.blob_service_client.get_container_client(
            self.container_name
        )
        blob_list = container_client.list_blobs(include="metadata")
        # sas = generate_blob_sas(account_name, container_name, blob.name,account_key=account_key,  permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        sas = generate_container_sas(
            self.account_name,
            self.container_name,
            user_delegation_key=self.user_delegation_key,
            account_key=self.account_key,
            permission="r",
            expiry=datetime.utcnow() + timedelta(hours=3),
        )
        files = []
        converted_files = {}
        for blob in blob_list:
            if not blob.name.startswith("converted/"):
                files.append(
                    {
                        "filename": blob.name,
                        "converted": (
                            blob.metadata.get("converted", "false") == "true"
                            if blob.metadata
                            else False
                        ),
                        "embeddings_added": (
                            blob.metadata.get("embeddings_added", "false") == "true"
                            if blob.metadata
                            else False
                        ),
                        "fullpath": f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}",
                        "converted_filename": (
                            blob.metadata.get("converted_filename", "")
                            if blob.metadata
                            else ""
                        ),
                        "converted_path": "",
                    }
                )
            else:
                converted_files[blob.name] = (
                    f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}"
                )

        for file in files:
            converted_filename = file.pop("converted_filename", "")
            if converted_filename in converted_files:
                file["converted"] = True
                file["converted_path"] = converted_files[converted_filename]

        return files

    def upsert_blob_metadata(self, file_name, metadata):
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )
        # Read metadata from the blob
        blob_metadata = blob_client.get_blob_properties().metadata
        # Update metadata
        blob_metadata.update(metadata)
        # Add metadata to the blob
        blob_client.set_blob_metadata(metadata=blob_metadata)

    def get_container_sas(self):
        # Generate a SAS URL to the container and return it
        return "?" + generate_container_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            user_delegation_key=self.user_delegation_key,
            account_key=self.account_key,
            permission="r",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

    def get_blob_sas(self, file_name):
        # Generate a SAS URL to the blob and return it
        return (
            f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_name}"
            + "?"
            + generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=file_name,
                user_delegation_key=self.user_delegation_key,
                account_key=self.account_key,
                permission="r",
                expiry=datetime.utcnow() + timedelta(hours=1),
            )
        )
