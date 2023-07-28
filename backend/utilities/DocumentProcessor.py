
import logging
from typing import List

from .AzureSearchHelper import AzureSearchHelper
from .DocumentLoading import DocumentLoading, LoadingSettings
from .DocumentChunking import DocumentChunking, ChunkingSettings
from .parser.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)

class Processor(ChunkingSettings, LoadingSettings):
    def __init__(self, document_type: str, chunking: ChunkingSettings, loading: LoadingSettings):
        self.document_type = document_type
        self.chunking = chunking
        self.loading = loading

class DocumentProcessor:
    def __init__(self):
        pass
            
    def process(self, source_url: str, processors: List[Processor]):
        vector_store_helper = AzureSearchHelper()
        vector_store = vector_store_helper.get_vector_store()
        for processor in processors:            
            try:
                document_loading = DocumentLoading()
                document_chunking = DocumentChunking()
                documents : List[SourceDocument] = []
                documents = document_loading.load(source_url, processor.loading)
                documents = document_chunking.chunk(documents, processor.chunking)
                keys = list(map(lambda x: x.id, documents))
                documents = [document.convert_to_langchain_document() for document in documents]
                return vector_store.add_documents(documents=documents, keys=keys)
            except Exception as e:
                logging.error(f"Error adding embeddings for {source_url}: {e}")
                raise e
