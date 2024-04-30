import logging
from langchain.vectorstores.azuresearch import AzureSearch
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SimpleField,
)
from .LLMHelper import LLMHelper
from .EnvHelper import EnvHelper
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    VectorSearch,
    VectorSearchProfile,
)


class AzureSearchHelper:
    _search_dimension: int | None = None

    def __init__(self):
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

        if self.env_helper.is_auth_type_keys:
            search_credential = AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
        else:
            search_credential = DefaultAzureCredential()

        logging.info(
            f"Creating search client for {self.env_helper.AZURE_SEARCH_SERVICE} and index {self.env_helper.AZURE_SEARCH_INDEX}"
        )

        self.search_client = SearchClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            index_name=self.env_helper.AZURE_SEARCH_INDEX,
            credential=search_credential,
        )
        self.search_index_client = SearchIndexClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE, credential=search_credential
        )

    @property
    def search_dimensions(self) -> int:
        if AzureSearchHelper._search_dimension is None:
            AzureSearchHelper._search_dimension = len(
                self.llm_helper.get_embedding_model().embed_query("Text")
            )
        return AzureSearchHelper._search_dimension

    def get_client(self):
        return self.search_client

    def create_or_update_index(self):
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
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
            SearchableField(
                name="title",
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
            ),
            SearchableField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="chunk",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SimpleField(
                name="offset",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
        ]

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
                                content_fields=[SemanticField(field_name="content")],
                            ),
                        )
                    ]
                )
                if self.env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH
                else None
            ),
            vector_search=VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="hnsw_config",
                        parameters=HnswParameters(metric="cosine"),
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name="myHnswProfile",
                        algorithm_configuration_name="hnsw_config",
                    ),
                ],
            ),
        )

        if self.env_helper.AZURE_SEARCH_INDEX not in [
            name for name in self.search_index_client.list_index_names()
        ]:
            try:
                logging.info(f"Creating index {self.env_helper.AZURE_SEARCH_INDEX}")
                self.search_index_client.create_index(index)
            except Exception as e:
                logging.exception("Error Creating index")
                raise e
        else:
            logging.info(f"Index {self.env_helper.AZURE_SEARCH_INDEX} already exists")

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

        return AzureSearch(
            azure_search_endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            azure_search_key=(
                self.env_helper.AZURE_SEARCH_KEY
                if self.env_helper.AZURE_AUTH_TYPE == "keys"
                else None
            ),
            index_name=self.env_helper.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
            embedding_function=self.llm_helper.get_embedding_model().embed_query,
            fields=fields,
            user_agent="langchain chatwithyourdata-sa",
        )
