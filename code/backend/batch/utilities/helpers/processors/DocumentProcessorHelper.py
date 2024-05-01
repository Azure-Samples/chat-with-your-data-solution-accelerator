import logging
from typing import List

from ..AzureBlobStorageHelper import AzureBlobStorageClient

from ..Processor import Processor
from ..ConfigHelper import ConfigHelper

from .ProcessorBase import ProcessorBase
from ..AzureSearchHelper import AzureSearchHelper
from ..DocumentLoadingHelper import DocumentLoading
from ..DocumentChunkingHelper import DocumentChunking
from ...common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class DocumentProcessor(ProcessorBase):
    def __init__(self, blob_client: AzureBlobStorageClient):
        self.blob_client = blob_client

    def process_file(self, source_url: str, file_name: str):
        file_extension = file_name.split(".")[-1]
        processors = [
            x
            for x in ConfigHelper.get_active_config_or_default().document_processors
            if x.document_type.lower() == file_extension.lower()
        ]
        self.process(source_url=source_url, processors=processors)
        if file_extension != "url":
            self.blob_client.upsert_blob_metadata(
                file_name, {"embeddings_added": "true"}
            )

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
