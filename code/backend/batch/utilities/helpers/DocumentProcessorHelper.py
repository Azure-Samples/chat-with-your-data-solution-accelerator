import logging
from typing import List

from ..integrated_vectorization.AzureSearchIndex import AzureSearchIndex
from ..integrated_vectorization.AzureSearchIndexer import AzureSearchIndexer
from ..integrated_vectorization.AzureSearchDatasource import AzureSearchDatasource
from ..integrated_vectorization.AzureSearchSkillset import AzureSearchSkillset
from .AzureSearchHelper import AzureSearchHelper
from .DocumentLoadingHelper import DocumentLoading, LoadingSettings
from .DocumentChunkingHelper import DocumentChunking, ChunkingSettings
from ..common.SourceDocument import SourceDocument
from .EnvHelper import EnvHelper
from .LLMHelper import LLMHelper

logger = logging.getLogger(__name__)


class Processor(ChunkingSettings, LoadingSettings):
    def __init__(
        self,
        document_type: str,
        chunking: ChunkingSettings | None,
        loading: LoadingSettings | None,
        use_advanced_image_processing: bool,
    ):
        self.document_type = document_type
        self.chunking = chunking
        self.loading = loading
        self.use_advanced_image_processing = use_advanced_image_processing

    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return (
                self.document_type == other.document_type
                and self.chunking == other.chunking
                and self.loading == other.loading
                and self.use_advanced_image_processing
                == other.use_advanced_image_processing
            )
        return False


class DocumentProcessor:
    def __init__(self):
        pass

    def process(self, source_url: str, processors: List[Processor]):
        vector_store_helper = AzureSearchHelper()
        vector_store = vector_store_helper.get_vector_store()
        for processor in processors:
            if not processor.use_advanced_image_processing:
                try:
                    document_loading = DocumentLoading()
                    document_chunking = DocumentChunking()
                    documents: List[SourceDocument] = []
                    documents = document_loading.load(source_url, processor.loading)
                    documents = document_chunking.chunk(documents, processor.chunking)
                    keys = list(map(lambda x: x.id, documents))
                    documents = [
                        document.convert_to_langchain_document()
                        for document in documents
                    ]
                    return vector_store.add_documents(documents=documents, keys=keys)
                except Exception as e:
                    logger.error(f"Error adding embeddings for {source_url}: {e}")
                    raise e
            else:
                logger.warn("Advanced image processing is not supported yet")

    def process_using_integrated_vectorisation(self, source_url: str):
        env_helper: EnvHelper = EnvHelper()
        llm_helper: LLMHelper = LLMHelper()
        try:
            search_datasource = AzureSearchDatasource(env_helper)
            search_datasource.create_or_update_datasource()
            search_index = AzureSearchIndex(env_helper, llm_helper)
            search_index.create_or_update_index()
            search_skillset = AzureSearchSkillset(env_helper)
            search_skillset_result = search_skillset.create_skillset()
            search_indexer = AzureSearchIndexer(env_helper)
            indexer_result = search_indexer.create_or_update_indexer(
                env_helper.AZURE_SEARCH_INDEXER_NAME,
                skillset_name=search_skillset_result.name,
            )
            return indexer_result
        except Exception as e:
            logger.error(f"Error processing {source_url}: {e}")
            raise e
