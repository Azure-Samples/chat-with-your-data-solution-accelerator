import hashlib
import json
import logging
from typing import List
from urllib.parse import urlparse

from ...helpers.llm_helper import LLMHelper
from ...helpers.env_helper import EnvHelper
from ..azure_computer_vision_client import AzureComputerVisionClient

from ..azure_blob_storage_client import AzureBlobStorageClient

from ..config.embedding_config import EmbeddingConfig
from ..config.config_helper import ConfigHelper

from .embedder_base import EmbedderBase
from ..azure_search_helper import AzureSearchHelper
from ..document_loading_helper import DocumentLoading
from ..document_chunking_helper import DocumentChunking
from ...common.source_document import SourceDocument

logger = logging.getLogger(__name__)


class PushEmbedder(EmbedderBase):
    def __init__(self, blob_client: AzureBlobStorageClient, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.llm_helper = LLMHelper()
        self.azure_search_helper = AzureSearchHelper()
        self.azure_computer_vision_client = AzureComputerVisionClient(env_helper)
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
            caption = self.__generate_image_caption(source_url)
            caption_vector = self.llm_helper.generate_embeddings(caption)

            image_vector = self.azure_computer_vision_client.vectorize_image(source_url)
            documents_to_upload.append(
                self.__create_image_document(
                    source_url, image_vector, caption, caption_vector
                )
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

        response = self.azure_search_helper.get_search_client().upload_documents(
            documents_to_upload
        )
        if not all([r.succeeded for r in response]):
            logger.error("Failed to upload documents to search index")
            raise Exception(response)

    def __generate_image_caption(self, source_url):
        model = self.env_helper.AZURE_OPENAI_VISION_MODEL
        caption_system_message = """You are an assistant that generates rich descriptions of images.
You need to be accurate in the information you extract and detailed in the descriptons you generate.
Do not abbreviate anything and do not shorten sentances. Explain the image completely.
If you are provided with an image of a flow chart, describe the flow chart in detail.
If the image is mostly text, use OCR to extract the text as it is displayed in the image."""

        messages = [
            {"role": "system", "content": caption_system_message},
            {
                "role": "user",
                "content": [
                    {
                        "text": "Describe this image in detail. Limit the response to 500 words.",
                        "type": "text",
                    },
                    {"image_url": {"url": source_url}, "type": "image_url"},
                ],
            },
        ]

        response = self.llm_helper.get_chat_completion(messages, model)
        caption = response.choices[0].message.content
        return caption

    def __convert_to_search_document(self, document: SourceDocument):
        embedded_content = self.llm_helper.generate_embeddings(document.content)
        metadata = {
            self.env_helper.AZURE_SEARCH_FIELDS_ID: document.id,
            self.env_helper.AZURE_SEARCH_SOURCE_COLUMN: document.source,
            self.env_helper.AZURE_SEARCH_TITLE_COLUMN: document.title,
            self.env_helper.AZURE_SEARCH_CHUNK_COLUMN: document.chunk,
            self.env_helper.AZURE_SEARCH_OFFSET_COLUMN: document.offset,
            "page_number": document.page_number,
            "chunk_id": document.chunk_id,
        }
        return {
            self.env_helper.AZURE_SEARCH_FIELDS_ID: document.id,
            self.env_helper.AZURE_SEARCH_CONTENT_COLUMN: document.content,
            self.env_helper.AZURE_SEARCH_CONTENT_VECTOR_COLUMN: embedded_content,
            self.env_helper.AZURE_SEARCH_FIELDS_METADATA: json.dumps(metadata),
            self.env_helper.AZURE_SEARCH_TITLE_COLUMN: document.title,
            self.env_helper.AZURE_SEARCH_SOURCE_COLUMN: document.source,
            self.env_helper.AZURE_SEARCH_CHUNK_COLUMN: document.chunk,
            self.env_helper.AZURE_SEARCH_OFFSET_COLUMN: document.offset,
        }

    def __generate_document_id(self, source_url: str) -> str:
        hash_key = hashlib.sha1(f"{source_url}_1".encode("utf-8")).hexdigest()
        return f"doc_{hash_key}"

    def __create_image_document(
        self,
        source_url: str,
        image_vector: List[float],
        content: str,
        content_vector: List[float],
    ):
        parsed_url = urlparse(source_url)

        file_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
        document_id = self.__generate_document_id(file_url)
        filename = parsed_url.path

        sas_placeholder = (
            "_SAS_TOKEN_PLACEHOLDER_"
            if parsed_url.netloc
            and parsed_url.netloc.endswith(".blob.core.windows.net")
            else ""
        )

        return {
            "id": document_id,
            "content": content,
            "content_vector": content_vector,
            "image_vector": image_vector,
            "metadata": json.dumps(
                {
                    "id": document_id,
                    "title": filename,
                    "source": file_url + sas_placeholder,
                }
            ),
            "title": filename,
            "source": file_url + sas_placeholder,
        }
