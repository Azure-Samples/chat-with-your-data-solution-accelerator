import logging
from typing import List

from ..AzureBlobStorageClient import AzureBlobStorageClient

from ..config.EmbeddingConfig import EmbeddingConfig
from ..config.ConfigHelper import ConfigHelper

from .EmbedderBase import EmbedderBase
from ..AzureSearchHelper import AzureSearchHelper
from ..DocumentLoadingHelper import DocumentLoading
from ..DocumentChunkingHelper import DocumentChunking
from ...common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class PushEmbedder(EmbedderBase):
    def __init__(self, blob_client: AzureBlobStorageClient):
        self.blob_client = blob_client
        config = ConfigHelper.get_active_config_or_default()
        self.processor_map = {}
        for processor in config.document_processors:
            ext = processor.document_type.lower()
            self.processor_map[ext] = processor

    def embed_file(self, source_url: str, file_name: str):
        file_extension = file_name.split(".")[-1]
        processor = self.processor_map.get(file_extension)
        self.__embed(source_url=source_url, processor=processor)
        if file_extension != "url":
            self.blob_client.upsert_blob_metadata(
                file_name, {"embeddings_added": "true"}
            )

    def __embed(self, source_url: str, processor: EmbeddingConfig):
        vector_store_helper = AzureSearchHelper()
        vector_store = vector_store_helper.get_vector_store()
        if not processor.use_advanced_image_processing:
            try:
                document_loading = DocumentLoading()
                document_chunking = DocumentChunking()
                documents: List[SourceDocument] = []
                documents = document_loading.load(source_url, processor.loading)
                documents = document_chunking.chunk(documents, processor.chunking)
                keys = list(map(lambda x: x.id, documents))
                documents = [
                    document.convert_to_langchain_document() for document in documents
                ]
                return vector_store.add_documents(documents=documents, keys=keys)
            except Exception as e:
                logger.error(f"Error adding embeddings for {source_url}: {e}")
                raise e
        else:
            logger.warn("Advanced image processing is not supported yet")
