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
        pass

    def create_or_update_datasource(self):
        env_helper: EnvHelper = EnvHelper()
        # Create a data source
        indexer_client = SearchIndexerClient(
            env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )
        container = SearchIndexerDataContainer(
            name=env_helper.AZURE_BLOB_CONTAINER_NAME
        )
        data_source_connection = SearchIndexerDataSourceConnection(
            name=env_helper.AZURE_SEARCH_DATASOURCE_NAME,
            type="azureblob",
            connection_string=f"DefaultEndpointsProtocol=https;AccountName={env_helper.AZURE_BLOB_ACCOUNT_NAME};AccountKey={env_helper.AZURE_BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net",
            container=container,
            data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
        )
        data_source = indexer_client.create_or_update_data_source_connection(
            data_source_connection
        )

        print(f"Data source '{data_source.name}' created or updated")
