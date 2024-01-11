from typing import Optional
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, generate_container_sas, ContentSettings, UserDelegationKey
from .EnvHelper import EnvHelper
from azure.identity import DefaultAzureCredential
import os

class AzureBlobStorageClient:
    def __init__(self, account_name: Optional[str] = None, account_key: Optional[str] = None, container_name: Optional[str] = None):

        env_helper : EnvHelper = EnvHelper()

        self.auth_type = env_helper.AUTH_TYPE
        if self.auth_type == 'rbac':
            self.account_name = account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
            self.container_name : str = container_name if container_name else env_helper.AZURE_BLOB_CONTAINER_NAME
            credential = DefaultAzureCredential()
            account_url = f"https://{self.account_name}.blob.core.windows.net/"
            self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
            self.user_delegation_key = self.request_user_delegation_key(blob_service_client=self.blob_service_client)
        else:
            self.account_name = account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
            self.account_key = account_key if account_key else env_helper.AZURE_BLOB_ACCOUNT_KEY
            self.connect_str = f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net"
            self.container_name : str = container_name if container_name else env_helper.AZURE_BLOB_CONTAINER_NAME
            self.blob_service_client : BlobServiceClient = BlobServiceClient.from_connection_string(self.connect_str)
    
    def request_user_delegation_key(self, blob_service_client: BlobServiceClient) -> UserDelegationKey:
        # Get a user delegation key that's valid for 1 day
        delegation_key_start_time = datetime.utcnow()
        delegation_key_expiry_time = delegation_key_start_time + timedelta(days=1)
    
        user_delegation_key = blob_service_client.get_user_delegation_key(
            key_start_time=delegation_key_start_time,
            key_expiry_time=delegation_key_expiry_time
        )
        return user_delegation_key
    
    def get_blob_sas_with_diff_key(self, file_name, auth_type):
        if auth_type == 'rbac':
            return generate_blob_sas(self.account_name, self.container_name, file_name, user_delegation_key=self.user_delegation_key, permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        else:
            return generate_blob_sas(self.account_name, self.container_name, file_name, account_key=self.account_key, permission="r", expiry=datetime.utcnow() + timedelta(hours=3))

    def get_container_sas_with_diff_key(self, auth_type):
        if auth_type == 'rbac':
            return generate_container_sas(self.account_name, self.container_name, user_delegation_key=self.user_delegation_key, permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        else:
            return generate_container_sas(self.account_name, self.container_name, account_key=self.account_key, permission="r", expiry=datetime.utcnow() + timedelta(hours=3))

    def upload_file(self, bytes_data, file_name, content_type='application/pdf'):
        # Create a blob client using the local file name as the name for the blob
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        # Upload the created file
        blob_client.upload_blob(bytes_data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
        # Generate a SAS URL to the blob and return it
        return blob_client.url + '?' + self.get_blob_sas_with_diff_key(file_name=file_name, auth_type=self.auth_type)

    def download_file(self, file_name):
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        return blob_client.download_blob().readall()
    
    def delete_file(self, file_name):
        """
        Deletes a file from the Azure Blob Storage container.

        Args:
            file_name (str): The name of the file to delete.

        Returns:
            None
        """
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        blob_client.delete_blob()

    def get_all_files(self):
        # Get all files in the container from Azure Blob Storage
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blob_list = container_client.list_blobs(include='metadata')
        # sas = generate_blob_sas(account_name, container_name, blob.name,account_key=account_key,  permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        sas = self.get_container_sas_with_diff_key(auth_type=self.auth_type)
        files = []
        converted_files = {}
        for blob in blob_list:
            if not blob.name.startswith('converted/'):
                files.append({
                    "filename" : blob.name,
                    "converted": blob.metadata.get('converted', 'false') == 'true' if blob.metadata else False,
                    "embeddings_added": blob.metadata.get('embeddings_added', 'false') == 'true' if blob.metadata else False,
                    "fullpath": f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}",
                    "converted_filename": blob.metadata.get('converted_filename', '') if blob.metadata else '',
                    "converted_path": ""
                    })
            else:
                converted_files[blob.name] = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}"

        for file in files:
            converted_filename = file.pop('converted_filename', '')
            if converted_filename in converted_files:
                file['converted'] = True
                file['converted_path'] = converted_files[converted_filename]
        
        return files

    def upsert_blob_metadata(self, file_name, metadata):
        if self.auth_type == 'rbac':
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        else:
            blob_client = BlobServiceClient.from_connection_string(self.connect_str).get_blob_client(container=self.container_name, blob=file_name)
        # Read metadata from the blob
        blob_metadata = blob_client.get_blob_properties().metadata
        # Update metadata
        blob_metadata.update(metadata)
        # Add metadata to the blob
        blob_client.set_blob_metadata(metadata= blob_metadata)

    def get_container_sas(self):
        # Generate a SAS URL to the container and return it
        return "?" + self.get_container_sas_with_diff_key(auth_type=self.auth_type)

    def get_blob_sas(self, file_name):
        # Generate a SAS URL to the blob and return it
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_name}" + "?" + self.get_blob_sas_with_diff_key(file_name=file_name, auth_type=self.auth_type)
