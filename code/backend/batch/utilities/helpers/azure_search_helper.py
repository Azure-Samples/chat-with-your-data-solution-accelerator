import logging
from typing import Union
from langchain_community.vectorstores import AzureSearch
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

from ..helpers.azure_computer_vision_client import AzureComputerVisionClient
from .llm_helper import LLMHelper
from .env_helper import EnvHelper

logger = logging.getLogger(__name__)


class AzureSearchHelper:
    _search_dimension: int | None = None
    _image_search_dimension: int | None = None

    def __init__(self):
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

        search_credential = self._search_credential()
        self.search_client = self._create_search_client(search_credential)
        self.search_index_client = self._create_search_index_client(search_credential)
        self.azure_computer_vision_client = AzureComputerVisionClient(self.env_helper)

    def _search_credential(self):
        if self.env_helper.is_auth_type_keys():
            return AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
        else:
            return DefaultAzureCredential()

    def _create_search_client(
        self, search_credential: Union[AzureKeyCredential, DefaultAzureCredential]
    ) -> SearchClient:
        return SearchClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            index_name=self.env_helper.AZURE_SEARCH_INDEX,
            credential=search_credential,
        )

    def _create_search_index_client(
        self, search_credential: Union[AzureKeyCredential, DefaultAzureCredential]
    ):
        return SearchIndexClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE, credential=search_credential
        )

    def get_search_client(self) -> SearchClient:
        self.create_index()
        return self.search_client

    @property
    def search_dimensions(self) -> int:
        if AzureSearchHelper._search_dimension is None:
            AzureSearchHelper._search_dimension = len(
                self.llm_helper.get_embedding_model().embed_query("Text")
            )
        return AzureSearchHelper._search_dimension

    @property
    def image_search_dimensions(self) -> int:
        if AzureSearchHelper._image_search_dimension is None:
            AzureSearchHelper._image_search_dimension = len(
                self.azure_computer_vision_client.vectorize_text("Text")
            )
        return AzureSearchHelper._image_search_dimension

    def create_index(self):
        fields = [
            SimpleField(
                name=self.env_helper.AZURE_SEARCH_FIELDS_ID,
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(
                name=self.env_helper.AZURE_SEARCH_CONTENT_COLUMN,
                type=SearchFieldDataType.String,
            ),
            SearchField(
                name=self.env_helper.AZURE_SEARCH_CONTENT_VECTOR_COLUMN,
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.search_dimensions,
                vector_search_profile_name="myHnswProfile",
            ),
            SearchableField(
                name=self.env_helper.AZURE_SEARCH_FIELDS_METADATA,
                type=SearchFieldDataType.String,
            ),
            SearchableField(
                name=self.env_helper.AZURE_SEARCH_TITLE_COLUMN,
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
            ),
            SearchableField(
                name=self.env_helper.AZURE_SEARCH_SOURCE_COLUMN,
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name=self.env_helper.AZURE_SEARCH_CHUNK_COLUMN,
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SimpleField(
                name=self.env_helper.AZURE_SEARCH_OFFSET_COLUMN,
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
        ]

        if self.env_helper.USE_ADVANCED_IMAGE_PROCESSING:
            logger.info("Adding image_vector field to index")
            fields.append(
                SearchField(
                    name="image_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self.image_search_dimensions,
                    vector_search_profile_name="myHnswProfile",
                ),
            )

        index = SearchIndex(
            name=self.env_helper.AZURE_SEARCH_INDEX,
            fields=fields,
            semantic_search=(
                SemanticSearch(
                    configurations=[
                        SemanticConfiguration(
                            name=self.env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
                            prioritized_fields=SemanticPrioritizedFields(
                                title_field=None,
                                content_fields=[
                                    SemanticField(
                                        field_name=self.env_helper.AZURE_SEARCH_CONTENT_COLUMN
                                    )
                                ],
                            ),
                        )
                    ]
                )
            ),
            vector_search=VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default",
                        parameters=HnswParameters(
                            metric=VectorSearchAlgorithmMetric.COSINE
                        ),
                        kind=VectorSearchAlgorithmKind.HNSW,
                    ),
                    ExhaustiveKnnAlgorithmConfiguration(
                        name="default_exhaustive_knn",
                        kind=VectorSearchAlgorithmKind.EXHAUSTIVE_KNN,
                        parameters=ExhaustiveKnnParameters(
                            metric=VectorSearchAlgorithmMetric.COSINE
                        ),
                    ),
                ],
                profiles=[
                    VectorSearchProfile(
                        name="myHnswProfile",
                        algorithm_configuration_name="default",
                    ),
                    VectorSearchProfile(
                        name="myExhaustiveKnnProfile",
                        algorithm_configuration_name="default_exhaustive_knn",
                    ),
                ],
            ),
        )

        if self._index_not_exists(self.env_helper.AZURE_SEARCH_INDEX):
            logger.info(
                f"Creating or updating index {self.env_helper.AZURE_SEARCH_INDEX}"
            )
            self.search_index_client.create_index(index)

    def _index_not_exists(self, index_name: str) -> bool:
        return index_name not in [
            name for name in self.search_index_client.list_index_names()
        ]

    def get_conversation_logger(self):
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SimpleField(
                name="conversation_id",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.search_dimensions,
                vector_search_profile_name="myHnswProfile",
            ),
            SearchableField(
                name="metadata",
                type=SearchFieldDataType.String,
            ),
            SimpleField(
                name="type",
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
            ),
            SimpleField(
                name="user_id",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="sources",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="created_at",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
            ),
            SimpleField(
                name="updated_at",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
            ),
        ]

        if self.env_helper.AZURE_AUTH_TYPE == "rbac":
            credential = DefaultAzureCredential()
            return AzureSearch(
                azure_search_endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
                azure_search_key=None,  # Remove API key
                index_name=self.env_helper.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
                embedding_function=self.llm_helper.get_embedding_model().embed_query,
                fields=fields,
                user_agent="langchain chatwithyourdata-sa",
                credential=credential  # Add token credential or send none so it is auto handled by AzureSearch library
            )
        else:
            return AzureSearch(
                azure_search_endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
                azure_search_key=(
                    self.env_helper.AZURE_SEARCH_KEY
                    if self.env_helper.is_auth_type_keys()
                    else None
                ),
                index_name=self.env_helper.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
                embedding_function=self.llm_helper.get_embedding_model().embed_query,
                fields=fields,
                user_agent="langchain chatwithyourdata-sa",
            )
