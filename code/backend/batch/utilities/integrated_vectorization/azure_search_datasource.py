from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
)
from azure.search.documents.indexes._generated.models import (
    NativeBlobSoftDeleteDeletionDetectionPolicy,
)
from azure.search.documents.indexes import SearchIndexerClient
from ..helpers.env_helper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential


class AzureSearchDatasource:
    def __init__(self, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.indexer_client = SearchIndexerClient(
            self.env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.is_auth_type_keys()
                else DefaultAzureCredential()
            ),
        )

    def create_or_update_datasource(self):
        connection_string = self.generate_datasource_connection_string()
        # Create Datasource
        container = SearchIndexerDataContainer(
            name=self.env_helper.AZURE_BLOB_CONTAINER_NAME
        )
        data_source_connection = SearchIndexerDataSourceConnection(
            name=self.env_helper.AZURE_SEARCH_DATASOURCE_NAME,
            type="azureblob",
            connection_string=connection_string,
            container=container,
            data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
        )
        self.indexer_client.create_or_update_data_source_connection(
            data_source_connection
        )

    def generate_datasource_connection_string(self):
        if self.env_helper.is_auth_type_keys():
            return f"DefaultEndpointsProtocol=https;AccountName={self.env_helper.AZURE_BLOB_ACCOUNT_NAME};AccountKey={self.env_helper.AZURE_BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net"
        else:
            return f"ResourceId=/subscriptions/{self.env_helper.AZURE_SUBSCRIPTION_ID}/resourceGroups/{self.env_helper.AZURE_RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/{self.env_helper.AZURE_BLOB_ACCOUNT_NAME}/;"
