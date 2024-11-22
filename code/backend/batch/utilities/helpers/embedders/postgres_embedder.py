import hashlib
import json
import logging
from typing import List
from urllib.parse import urlparse

from ...helpers.llm_helper import LLMHelper
from ...helpers.env_helper import EnvHelper
from ...helpers.azure_postgres_helper import AzurePostgresHandler
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
        documents_to_upload: List[SourceDocument] = []
        if (
            embedding_config.use_advanced_image_processing
            and file_extension
            in self.config.get_advanced_image_processing_image_types()
        ):
            raise NotImplementedError(
                "Advanced image processing is not supported in PostgresEmbedder."
            )
        else:
            documents: List[SourceDocument] = self.document_loading.load(
                source_url, embedding_config.loading
            )
            documents = self.document_chunking.chunk(
                documents, embedding_config.chunking
            )

            for document in documents:
                documents_to_upload.append(self.__convert_to_search_document(document))
        # TODO fix this
        # Upload documents (which are chunks) to search index in batches
        if documents_to_upload:
            search_client = self.azure_postgres_handler.get_search_client()
            cur = search_client.cursor()
            for d in documents_to_upload:
                # SourceDocument
                #  self.id = id
                # self.content = content
                # self.source = source
                # self.title = title
                # self.chunk = chunk
                # self.offset = offset
                # self.page_number = page_number
                # self.chunk_id = chunk_id

                # table
                # id text,
                # title text,
                # chunk integer,
                # chunk_id text,
                # "offset" integer,
                # page_number integer,
                # content text,
                # source text,
                # metadata text,
                # content_vector vector(1536)O
                # TODO FIX THIS
                content_vector = get_embeddings(
                    d["content"], openai_api_base, openai_api_version, openai_api_key
                )
                cur.execute(
                    f"INSERT INTO search_indexes (id,title,chunk,chunk_id,offset,page_number,content,source,metadata,content_vector) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        d.id,
                        d.title,
                        d.chunk,
                        d.chunk_id,
                        d.offset,
                        d.page_number,
                        d.content,
                        d.source,
                        json.dumps("TBD"),
                        content_vector,
                    ),
                )
            cur.close()
            search_client.commit()
        else:
            logger.warning("No documents to upload.")
