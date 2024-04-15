from azure.search.documents.indexes.models import SearchIndexer, FieldMapping
from azure.search.documents.indexes import SearchIndexerClient
from .EnvHelper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential


class AzureSearchIVIndexerHelper:
    def __init__(self):
        pass

    def create_or_update_indexer(self, indexer_name: str, skillset_name: str):
        env_helper: EnvHelper = EnvHelper()
        indexer = SearchIndexer(
            name=indexer_name,
            description="Indexer to index documents and generate embeddings",
            skillset_name=skillset_name,
            target_index_name=env_helper.AZURE_SEARCH_INDEX,
            data_source_name=env_helper.AZURE_SEARCH_DATASOURCE_NAME,
            # Map the metadata_storage_name field to the title field in the index to display the PDF title in the search results
            field_mappings=[
                FieldMapping(
                    source_field_name="metadata_storage_name", target_field_name="title"
                )
            ],
        )

        indexer_client = SearchIndexerClient(
            env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )
        indexer_client.create_or_update_indexer(indexer)
        # indexer_client.get_indexer_names().__contains__(indexer_name)

        # Run the indexer
        indexer_client.run_indexer(indexer_name)
        print(
            f" {indexer_name} is created and running. If queries return no results, please wait a bit and try again."
        )

    def run_indexer(self, indexer_name: str):
        env_helper: EnvHelper = EnvHelper()
        indexer_client = SearchIndexerClient(
            env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )
        indexer_client.run_indexer(indexer_name)
        print(
            f" {indexer_name} is created and running. If queries return no results, please wait a bit and try again."
        )
