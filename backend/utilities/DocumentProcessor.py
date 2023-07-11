
import os
from dotenv import load_dotenv
import logging
from typing import List

from langchain.vectorstores.base import VectorStore

from .azuresearch import AzureSearch
from .LLMHelper import LLMHelper
from .DocumentLoading import DocumentLoading, Loading
from .DocumentChunking import DocumentChunking, Chunking

logger = logging.getLogger(__name__)

class Processor(Chunking, Loading):
    def __init__(self, document_type: str, chunking: Chunking, loading: Loading):
        self.document_type = document_type
        self.chunking = chunking
        self.loading = loading

class DocumentProcessor:
    def __init__(self):
        load_dotenv()        
        # Azure Search settings
        self.azure_search_endpoint: str = os.getenv("AZURE_SEARCH_SERVICE")
        self.azure_search_key: str = os.getenv("AZURE_SEARCH_KEY")
        self.index_name: str = os.getenv("AZURE_SEARCH_INDEX")
        self.embeddings = LLMHelper().get_embedding_model()
        self.vector_store: AzureSearch = AzureSearch(
                azure_cognitive_search_name=self.azure_search_endpoint,
                azure_cognitive_search_key=self.azure_search_key,
                index_name=self.index_name,
                embedding_function=self.embeddings.embed_query)
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
