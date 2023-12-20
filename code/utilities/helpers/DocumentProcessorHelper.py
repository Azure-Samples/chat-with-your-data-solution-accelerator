import logging
from typing import List
from .AzureSearchHelper import AzureSearchHelper
from .DocumentLoadingHelper import DocumentLoading, LoadingSettings
from .DocumentChunkingHelper import DocumentChunking, ChunkingSettings
from ..common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class Processor(ChunkingSettings, LoadingSettings):
    """
    Processor class for handling document processing.

    Args:
        document_type (str): The type of document being processed.
        chunking (ChunkingSettings): The settings for chunking the document.
        loading (LoadingSettings): The settings for loading the document.

    Attributes:
        document_type (str): The type of document being processed.
        chunking (ChunkingSettings): The settings for chunking the document.
        loading (LoadingSettings): The settings for loading the document.
    """

    def __init__(self, document_type: str, chunking: ChunkingSettings, loading: LoadingSettings):
        self.document_type = document_type
        self.chunking = chunking
        self.loading = loading


class DocumentProcessor:
    """
    Class responsible for processing documents.

    Args:
        source_url (str): The URL of the source document.
        processors (List[Processor]): List of processors to apply.

    Returns:
        bool: True if the documents are successfully processed and added to the vector store.

    Raises:
        Exception: If an error occurs while adding embeddings to the vector store.
    """

    def __init__(self):
        pass

    def process(self, source_url: str, processors: List[Processor]):
        """
        Process the source documents by loading, chunking, and adding embeddings to the vector store.

        Args:
            source_url (str): The URL of the source documents.
            processors (List[Processor]): The list of processors to apply.

        Returns:
            bool: True if the documents were successfully added to the vector store, False otherwise.

        Raises:
            Exception: If an error occurs while adding embeddings to the vector store.
        """
        vector_store_helper = AzureSearchHelper()
        vector_store = vector_store_helper.get_vector_store()
        for processor in processors:
            try:
                document_loading = DocumentLoading()
                document_chunking = DocumentChunking()
                documents: List[SourceDocument] = []
                documents = document_loading.load(
                    source_url, processor.loading)
                documents = document_chunking.chunk(
                    documents, processor.chunking)
                keys = list(map(lambda x: x.id, documents))
                documents = [document.convert_to_langchain_document()
                            for document in documents]
                return vector_store.add_documents(documents=documents, keys=keys)
            except Exception as e:
                logging.error(f"Error adding embeddings for {source_url}: {e}")
                raise e
