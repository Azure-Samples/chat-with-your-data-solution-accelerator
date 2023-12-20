from typing import Optional
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, generate_container_sas, ContentSettings
from .EnvHelper import EnvHelper


class AzureBlobStorageClient:
    """
    A client class for interacting with Azure Blob Storage.

    Args: account_name (str, optional): The name of the Azure Blob Storage account. If not provided, it will be
    fetched from the environment variables. account_key (str, optional): The access key for the Azure Blob Storage
    account. If not provided, it will be fetched from the environment variables. container_name (str, optional): The
    name of the container in Azure Blob Storage. If not provided, it will be fetched from the environment variables.
    """

    def __init__(self, account_name: Optional[str] = None, account_key: Optional[str] = None,
                 container_name: Optional[str] = None):

        env_helper: EnvHelper = EnvHelper()

        self.account_name = account_name if account_name else env_helper.AZURE_BLOB_ACCOUNT_NAME
        self.account_key = account_key if account_key else env_helper.AZURE_BLOB_ACCOUNT_KEY
        self.connect_str = f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net"
        self.container_name: str = container_name if container_name else env_helper.AZURE_BLOB_CONTAINER_NAME
        self.blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(self.connect_str)

    def upload_file(self, bytes_data, file_name, content_type='application/pdf'):
        """
            Uploads a file to Azure Blob Storage.

            Args:
                bytes_data (bytes): The file data in bytes format.
                file_name (str): The name of the file.
                content_type (str, optional): The content type of the file. Defaults to 'application/pdf'.

            Returns:
                str: The SAS URL of the uploaded file.
            """
        # Create a blob client using the local file name as the name for the blob
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
        # Upload the created file
        blob_client.upload_blob(bytes_data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
        # Generate a SAS URL to the blob and return it
        return blob_client.url + '?' + generate_blob_sas(self.account_name, self.container_name, file_name,
                                                         account_key=self.account_key, permission="r",
                                                         expiry=datetime.utcnow() + timedelta(hours=3))

    def download_file(self, file_name):
        """
            Downloads a file from Azure Blob Storage.

            Args:
                file_name (str): The name of the file to download.

            Returns:
                bytes: The content of the downloaded file.
            """
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
        """
            Retrieves a list of all files in the container from Azure Blob Storage.

            Returns:
                A list of dictionaries, where each dictionary represents a file in the container.
                Each dictionary contains the following keys:
                    - "filename": The name of the file.
                    - "converted": A boolean indicating if the file has been converted.
                    - "embeddings_added": A boolean indicating if embeddings have been added to the file.
                    - "fullpath": The full URL of the file in Azure Blob Storage.
                    - "converted_filename": The name of the converted file, if applicable.
                    - "converted_path": The full URL of the converted file, if applicable.
            """
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blob_list = container_client.list_blobs(include='metadata')
        sas = generate_container_sas(self.account_name, self.container_name, account_key=self.account_key,
                                     permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
        files = []
        converted_files = {}
        for blob in blob_list:
            if not blob.name.startswith('converted/'):
                files.append({
                    "filename": blob.name,
                    "converted": blob.metadata.get('converted', 'false') == 'true' if blob.metadata else False,
                    "embeddings_added": blob.metadata.get('embeddings_added',
                                                          'false') == 'true' if blob.metadata else False,
                    "fullpath": f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}",
                    "converted_filename": blob.metadata.get('converted_filename', '') if blob.metadata else '',
                    "converted_path": ""
                })
            else:
                converted_files[
                    blob.name] = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}?{sas}"

        for file in files:
            converted_filename = file.pop('converted_filename', '')
            if converted_filename in converted_files:
                file['converted'] = True
                file['converted_path'] = converted_files[converted_filename]

        return files

    def upsert_blob_metadata(self, file_name, metadata):
        """
        Upserts the metadata of a blob in Azure Blob Storage.

        Args:
            file_name (str): The name of the blob file.
            metadata (dict): The metadata to be updated or added.

        Returns:
            None
        """
        blob_client = BlobServiceClient.from_connection_string(self.connect_str).get_blob_client(
            container=self.container_name, blob=file_name)
        # Read metadata from the blob
        blob_metadata = blob_client.get_blob_properties().metadata
        # Update metadata
        blob_metadata.update(metadata)
        # Add metadata to the blob
        blob_client.set_blob_metadata(metadata=blob_metadata)

    def get_container_sas(self):
        """
            Generates a Shared Access Signature (SAS) URL for the container.

            Returns:
                str: The SAS URL for the container.
            """
        # Generate a SAS URL to the container and return it
        return "?" + generate_container_sas(account_name=self.account_name, container_name=self.container_name,
                                            account_key=self.account_key, permission="r",
                                            expiry=datetime.utcnow() + timedelta(hours=1))

    def get_blob_sas(self, file_name):
        """
        Generates a Shared Access Signature (SAS) URL for the specified blob file.

        Parameters:
        - file_name (str): The name of the blob file.

        Returns:
        - str: The SAS URL for the blob file.
        """
        # Generate a SAS URL to the blob and return it
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{file_name}" + "?" + generate_blob_sas(
            account_name=self.account_name, container_name=self.container_name, blob_name=file_name,
            account_key=self.account_key, permission='r', expiry=datetime.utcnow() + timedelta(hours=1))
