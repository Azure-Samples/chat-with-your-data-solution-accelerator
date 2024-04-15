from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
)
from azure.search.documents.indexes._generated.models import (
    NativeBlobSoftDeleteDeletionDetectionPolicy,
)
from azure.search.documents.indexes import SearchIndexerClient
from .EnvHelper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential


class AzureSearchIVDatasourceHelper:
    def __init__(self):
        self.env_helper = EnvHelper()
        self.indexer_client = SearchIndexerClient(
            self.env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )

    def create_or_update_datasource(self):
        # Create Datasource
        container = SearchIndexerDataContainer(
            name=self.env_helper.AZURE_BLOB_CONTAINER_NAME
        )
        data_source_connection = SearchIndexerDataSourceConnection(
            name=self.env_helper.AZURE_SEARCH_DATASOURCE_NAME,
            type="azureblob",
            connection_string=f"DefaultEndpointsProtocol=https;AccountName={self.env_helper.AZURE_BLOB_ACCOUNT_NAME};AccountKey={self.env_helper.AZURE_BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net",
            container=container,
            data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
        )
        self.indexer_client.create_or_update_data_source_connection(
            data_source_connection
        )
