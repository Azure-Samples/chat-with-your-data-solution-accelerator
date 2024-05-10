import json
import logging
from typing import List

from ...helpers.llm_helper import LLMHelper

from ..azure_blob_storage_client import AzureBlobStorageClient

from ..config.embedding_config import EmbeddingConfig
from ..config.config_helper import ConfigHelper

from .embedder_base import EmbedderBase
from ..azure_search_helper import AzureSearchHelper
from ..document_loading_helper import DocumentLoading
from ..document_chunking_helper import DocumentChunking
from ...common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class PushEmbedder(EmbedderBase):
    def __init__(self, blob_client: AzureBlobStorageClient):
        self.llm_helper = LLMHelper()
        self.azure_search_helper = AzureSearchHelper()
        self.document_loading = DocumentLoading()
        self.document_chunking = DocumentChunking()
        self.blob_client = blob_client
        config = ConfigHelper.get_active_config_or_default()
        self.embedding_configs = {}
        for processor in config.document_processors:
            ext = processor.document_type.lower()
            self.embedding_configs[ext] = processor

    def embed_file(self, source_url: str, file_name: str):
        file_extension = file_name.split(".")[-1]
        embedding_config = self.embedding_configs.get(file_extension)
        self.__embed(source_url=source_url, embedding_config=embedding_config)
        if file_extension != "url":
            self.blob_client.upsert_blob_metadata(
                file_name, {"embeddings_added": "true"}
            )

    def __embed(self, source_url: str, embedding_config: EmbeddingConfig):
        documents_to_upload: List[SourceDocument] = []
        if not embedding_config.use_advanced_image_processing:
            documents: List[SourceDocument] = self.document_loading.load(
                source_url, embedding_config.loading
            )
            documents = self.document_chunking.chunk(
                documents, embedding_config.chunking
            )

            for document in documents:
                documents_to_upload.append(self._convert_to_search_document(document))

            response = self.azure_search_helper.get_search_client().upload_documents(
                documents_to_upload
            )
            if not all([r.succeeded for r in response]):
                raise Exception(response)

        else:
            logger.warning("Advanced image processing is not supported yet")

    def _convert_to_search_document(self, document: SourceDocument):
        embedded_content = self.llm_helper.generate_embeddings(document.content)
        metadata = {
            "id": document.id,
            "source": document.source,
            "title": document.title,
            "chunk": document.chunk,
            "offset": document.offset,
            "page_number": document.page_number,
            "chunk_id": document.chunk_id,
        }
        return {
            "id": document.id,
            "content": document.content,
            "content_vector": embedded_content,
            "metadata": json.dumps(metadata),
            "title": document.title,
            "source": document.source,
            "chunk": document.chunk,
            "offset": document.offset,
        }
