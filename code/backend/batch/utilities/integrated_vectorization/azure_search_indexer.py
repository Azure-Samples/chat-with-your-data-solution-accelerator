import logging
from azure.search.documents.indexes.models import SearchIndexer, FieldMapping
from azure.search.documents.indexes import SearchIndexerClient
from ..helpers.env_helper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class AzureSearchIndexer:
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

    def create_or_update_indexer(self, indexer_name: str, skillset_name: str):
        indexer = SearchIndexer(
            name=indexer_name,
            description="Indexer to index documents and generate embeddings",
            skillset_name=skillset_name,
            target_index_name=self.env_helper.AZURE_SEARCH_INDEX,
            data_source_name=self.env_helper.AZURE_SEARCH_DATASOURCE_NAME,
            field_mappings=[
                FieldMapping(
                    source_field_name="metadata_storage_path",
                    target_field_name="source",
                ),
            ],
        )
        indexer_result = self.indexer_client.create_or_update_indexer(indexer)
        # Run the indexer
        self.indexer_client.run_indexer(indexer_name)
        logger.info(
            f" {indexer_name} is created and running. If queries return no results, please wait a bit and try again."
        )
        return indexer_result

    def run_indexer(self, indexer_name: str):
        self.indexer_client.reset_indexer(indexer_name)
        self.indexer_client.run_indexer(indexer_name)
        logger.info(
            f" {indexer_name} is created and running. If queries return no results, please wait a bit and try again."
        )

    def indexer_exists(self, indexer_name: str):
        return indexer_name in [
            name for name in self.indexer_client.get_indexer_names()
        ]
