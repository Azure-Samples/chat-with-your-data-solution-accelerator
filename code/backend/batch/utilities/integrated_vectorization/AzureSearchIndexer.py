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

    def reprocess_all(self, indexer_name: str):
        reprocess_response = {"status": "success"}
        if indexer_name in [name for name in self.indexer_client.get_indexer_names()]:
            self.indexer_client.reset_indexer(indexer_name)
            run_response = self.indexer_client.run_indexer(indexer_name)
            logger.info(
                f" {indexer_name} is created and running. If queries return no results, please wait a bit and try again."
            )
            return reprocess_response if run_response is None else {"status": "error"}
        else:
            logger.error(f"Indexer {indexer_name} not found.")
            reprocess_response = {"status": "error"}
            return reprocess_response
