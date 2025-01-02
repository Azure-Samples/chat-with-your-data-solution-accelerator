import json
import logging
from typing import List

from ...helpers.llm_helper import LLMHelper
from ...helpers.env_helper import EnvHelper
from ..azure_blob_storage_client import AzureBlobStorageClient

from ..config.embedding_config import EmbeddingConfig
from ..config.config_helper import ConfigHelper

from .embedder_base import EmbedderBase
from ..azure_postgres_helper import AzurePostgresHelper
from ..document_loading_helper import DocumentLoading
from ..document_chunking_helper import DocumentChunking
from ...common.source_document import SourceDocument

logger = logging.getLogger(__name__)


class PostgresEmbedder(EmbedderBase):
    def __init__(self, blob_client: AzureBlobStorageClient, env_helper: EnvHelper):
        logger.info("Initializing PostgresEmbedder.")
        self.env_helper = env_helper
        self.llm_helper = LLMHelper()
        self.azure_postgres_helper = AzurePostgresHelper()
        self.document_loading = DocumentLoading()
        self.document_chunking = DocumentChunking()
        self.blob_client = blob_client
        self.config = ConfigHelper.get_active_config_or_default()
        self.embedding_configs = {}
        for processor in self.config.document_processors:
            ext = processor.document_type.lower()
            self.embedding_configs[ext] = processor

    def embed_file(self, source_url: str, file_name: str):
        logger.info(f"Embedding file: {file_name} from source: {source_url}")
        file_extension = file_name.split(".")[-1].lower()
        embedding_config = self.embedding_configs.get(file_extension)
        self.__embed(
            source_url=source_url,
            file_extension=file_extension,
            embedding_config=embedding_config,
        )
        if file_extension != "url":
            self.blob_client.upsert_blob_metadata(
                file_name, {"embeddings_added": "true"}
            )

    def __embed(
        self, source_url: str, file_extension: str, embedding_config: EmbeddingConfig
    ):
        logger.info(f"Starting embedding process for source: {source_url}")
        documents_to_upload: List[SourceDocument] = []
        if (
            embedding_config.use_advanced_image_processing
            and file_extension
            in self.config.get_advanced_image_processing_image_types()
        ):
            logger.error(
                "Advanced image processing is not supported in PostgresEmbedder."
            )
            raise NotImplementedError(
                "Advanced image processing is not supported in PostgresEmbedder."
            )
        else:
            logger.info(f"Loading documents from source: {source_url}")
            documents: List[SourceDocument] = self.document_loading.load(
                source_url, embedding_config.loading
            )
            documents = self.document_chunking.chunk(
                documents, embedding_config.chunking
            )
            logger.info("Chunked into document chunks.")

            for document in documents:
                documents_to_upload.append(self.__convert_to_search_document(document))

        if documents_to_upload:
            logger.info(
                f"Uploading {len(documents_to_upload)} documents to vector store."
            )
            self.azure_postgres_helper.create_vector_store(documents_to_upload)
        else:
            logger.warning("No documents to upload.")

    def __convert_to_search_document(self, document: SourceDocument):
        logger.info(f"Generating embeddings for document ID: {document.id}")
        embedded_content = self.llm_helper.generate_embeddings(document.content)
        metadata = {
            "id": document.id,
            "source": document.source,
            "title": document.title,
            "chunk": document.chunk,
            "chunk_id": document.chunk_id,
            "offset": document.offset,
            "page_number": document.page_number,
        }
        logger.info(f"Metadata generated for document ID: {document.id}")
        return {
            "id": document.id,
            "content": document.content,
            "content_vector": embedded_content,
            "metadata": json.dumps(metadata),
            "title": document.title,
            "source": document.source,
            "chunk": document.chunk,
            "chunk_id": document.chunk_id,
            "offset": document.offset,
            "page_number": document.page_number,
        }
