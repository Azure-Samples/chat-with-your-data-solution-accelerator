from .embedder_base import EmbedderBase
from ..env_helper import EnvHelper
from ..llm_helper import LLMHelper
from ...integrated_vectorization.azure_search_index import AzureSearchIndex
from ...integrated_vectorization.azure_search_indexer import AzureSearchIndexer
from ...integrated_vectorization.azure_search_datasource import AzureSearchDatasource
from ...integrated_vectorization.azure_search_skillset import AzureSearchSkillset
from ..config.config_helper import ConfigHelper
import logging

logger = logging.getLogger(__name__)


class IntegratedVectorizationEmbedder(EmbedderBase):
    def __init__(self, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.llm_helper: LLMHelper = LLMHelper()
        logger.info("Initialized IntegratedVectorizationEmbedder.")

    def embed_file(self, source_url: str, file_name: str = None):
        logger.info(
            f"Starting embed_file for source_url: {source_url}, file_name: {file_name}."
        )
        self.process_using_integrated_vectorization(source_url=source_url)

    def process_using_integrated_vectorization(self, source_url: str):
        logger.info(f"Starting integrated vectorization for source_url: {source_url}.")
        config = ConfigHelper.get_active_config_or_default()
        try:
            search_datasource = AzureSearchDatasource(self.env_helper)
            search_datasource.create_or_update_datasource()
            search_index = AzureSearchIndex(self.env_helper, self.llm_helper)
            search_index.create_or_update_index()
            search_skillset = AzureSearchSkillset(
                self.env_helper, config.integrated_vectorization_config
            )
            search_skillset_result = search_skillset.create_skillset()
            search_indexer = AzureSearchIndexer(self.env_helper)
            indexer_result = search_indexer.create_or_update_indexer(
                self.env_helper.AZURE_SEARCH_INDEXER_NAME,
                skillset_name=search_skillset_result.name,
            )
            logger.info("Integrated vectorization process completed successfully.")
            return indexer_result
        except Exception as e:
            logger.error(f"Error processing {source_url}: {e}")
            raise e

    def reprocess_all(self):
        logger.info("Starting reprocess_all operation.")
        search_indexer = AzureSearchIndexer(self.env_helper)
        if search_indexer.indexer_exists(self.env_helper.AZURE_SEARCH_INDEXER_NAME):
            logger.info(
                f"Running indexer: {self.env_helper.AZURE_SEARCH_INDEXER_NAME}."
            )
            search_indexer.run_indexer(self.env_helper.AZURE_SEARCH_INDEXER_NAME)
        else:
            logger.info("Indexer does not exist. Starting full processing.")
            self.process_using_integrated_vectorization(source_url="all")
