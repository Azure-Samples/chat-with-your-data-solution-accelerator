
import logging
from typing import List

from langchain.vectorstores.base import VectorStore

from .azuresearch import AzureSearch
from .LLMHelper import LLMHelper
from .DocumentLoading import DocumentLoading, Loading
from .DocumentChunking import DocumentChunking, Chunking
from .EnvHelper import EnvHelper

logger = logging.getLogger(__name__)

class Processor(Chunking, Loading):
    def __init__(self, document_type: str, chunking: Chunking, loading: Loading):
        self.document_type = document_type
        self.chunking = chunking
        self.loading = loading

class DocumentProcessor:
    def __init__(self):
        env_helper = EnvHelper()
        # Azure Search settings
        self.vector_store: AzureSearch = AzureSearch(
                azure_cognitive_search_name=  env_helper.AZURE_SEARCH_SERVICE,
                azure_cognitive_search_key= env_helper.AZURE_SEARCH_KEY,
                index_name= env_helper.AZURE_SEARCH_INDEX,
                embedding_function=LLMHelper().get_embedding_model().embed_query)
        self.k: int = 4
        
    def process(self, source_url: str, processors: List[Processor]):
        for processor in processors:            
            try:
                document_loading = DocumentLoading()
                document_chunking = DocumentChunking()
                documents = document_loading.load(source_url, processor.loading)
                documents = document_chunking.chunk(documents, processor.chunking)
                keys = list(map(lambda x: x.metadata['key'], documents))
                return self.vector_store.add_documents(documents=documents, keys=keys)
            except Exception as e:
                logging.error(f"Error adding embeddings for {source_url}: {e}")
                raise e
