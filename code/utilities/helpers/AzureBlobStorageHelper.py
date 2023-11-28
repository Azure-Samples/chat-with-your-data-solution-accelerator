from typing import Optional
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, generate_container_sas, ContentSettings
from azure.identity import DefaultAzureCredential
from .EnvHelper import EnvHelper

class AzureBlobStorageClient:
    def __init__(self, account_name: Optional[str] = None, account_key: Optional[str] = None, container_name: Optional[str] = None):

        env_helper : EnvHelper = EnvHelper()

        self.account_name = account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
        self.container_name: str = container_name if container_name else env_helper.AZURE_BLOB_CONTAINER_NAME
        
        self.account_key = account_key if account_key else env_helper.AZURE_BLOB_ACCOUNT_KEY
        self.blob_service_client = None
        if self.account_key:
            print(self.account_key)
            self.connect_str = f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net"
            self.blob_service_client : BlobServiceClient = BlobServiceClient.from_connection_string(self.connect_str)
        else:
            self.blob_service_client: BlobServiceClient = BlobServiceClient(account_url=f"https://{self.account_name}.blob.core.windows.net", credential=DefaultAzureCredential())
        
    def upload_file(self, bytes_data, file_name, content_type='application/pdf'):
        # Create a blob client using the local file name as the name for the blob
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        # Upload the created file
        blob_client.upload_blob(bytes_data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
        # Generate a SAS URL to the blob and return it
        if self.account_key:
            return blob_client.url + '?' + generate_blob_sas(self.account_name, self.container_name, file_name, permission="r", expiry=datetime.utcnow() + timedelta(hours=3))

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
        if self.account_key:
            sas = generate_container_sas(self.account_name, self.container_name,account_key=self.account_key,  permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        else:
            sas = None
        files = []
        converted_files = {}
        for blob in blob_list:
            if not blob.name.startswith('converted/'):
                if sas:
                    fullpath = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}"
                else:
                    fullpath = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}"
                files.append({
                    "filename" : blob.name,
                    "converted": blob.metadata.get('converted', 'false') == 'true' if blob.metadata else False,
                    "embeddings_added": blob.metadata.get('embeddings_added', 'false') == 'true' if blob.metadata else False,
                    "fullpath": fullpath,
                    "converted_filename": blob.metadata.get('converted_filename', '') if blob.metadata else '',
                    "converted_path": ""
                    })
            else:
                converted_files[blob.name] = fullpath

        for file in files:
            converted_filename = file.pop('converted_filename', '')
            if converted_filename in converted_files:
                file['converted'] = True
                file['converted_path'] = converted_files[converted_filename]
        
        return files

    def upsert_blob_metadata(self, file_name, metadata):
        # Read metadata from the blob
        if self.connect_str:
            blob_client = BlobServiceClient.from_connection_string(self.connect_str).get_blob_client(container=self.container_name, blob=file_name)
        else:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        blob_metadata = blob_client.get_blob_properties().metadata
        # Update metadata
        blob_metadata.update(metadata)
        # Add metadata to the blob
        blob_client.set_blob_metadata(metadata= blob_metadata)

    def get_container_sas(self):
        # Generate a SAS URL to the container and return it
        return "?" + generate_container_sas(account_name= self.account_name, container_name= self.container_name,account_key=self.account_key,  permission="r", expiry=datetime.utcnow() + timedelta(hours=1))

    def get_blob_sas(self, file_name):
        # Generate a SAS URL to the blob and return it
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_name}" + "?" + generate_blob_sas(account_name= self.account_name, container_name=self.container_name, blob_name= file_name, account_key= self.account_key, permission='r', expiry=datetime.utcnow() + timedelta(hours=1))
