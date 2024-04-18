import logging
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmMetric,
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIParameters,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex,
)
from .EnvHelper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class AzureSearchIVIndexHelper:
    def __init__(self, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.index_client = SearchIndexClient(
            self.env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )

    def create_or_update_index(self):
        # Create a search index
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                filterable=True,
                # key=True
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=1536,
                vector_search_profile_name="myHnswProfile",
            ),
            SearchableField(name="metadata", type=SearchFieldDataType.String),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(
                name="source", type=SearchFieldDataType.String, filterable=True
            ),
            SimpleField(
                name="chunk",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SimpleField(name="offset", type=SearchFieldDataType.Int32, filterable=True),
            SearchField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                sortable=True,
                filterable=True,
                facetable=True,
                analyzer_name="keyword",
            ),
        ]

        # Configure the vector search configuration
        vector_search = self.get_vector_search_config()

        # Configure the semantic search configuration
        semantic_search = self.get_semantic_search_config()

        # Create the search index
        index = SearchIndex(
            name=self.env_helper.AZURE_SEARCH_INDEX,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )
        result = self.index_client.create_or_update_index(index)
        logger.info(f"{result.name} index created successfully.")
        return result

    def get_vector_search_config(self):
        if self.env_helper.AZURE_AUTH_TYPE == "keys":
            azure_open_ai_parameters = AzureOpenAIParameters(
                resource_uri=self.env_helper.AZURE_OPENAI_ENDPOINT,
                deployment_id=self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
                api_key=self.env_helper.OPENAI_API_KEY,
            )
        else:
            azure_open_ai_parameters = AzureOpenAIParameters(
                resource_uri=self.env_helper.AZURE_OPENAI_ENDPOINT,
                deployment_id=self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
            )

        # Configure the vector search configuration
        return VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="myHnsw",
                    parameters=HnswParameters(
                        m=4,
                        ef_construction=400,
                        ef_search=500,
                        metric=VectorSearchAlgorithmMetric.COSINE,
                    ),
                ),
                ExhaustiveKnnAlgorithmConfiguration(
                    name="myExhaustiveKnn",
                    parameters=ExhaustiveKnnParameters(
                        metric=VectorSearchAlgorithmMetric.COSINE,
                    ),
                ),
            ],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw",
                    vectorizer="myOpenAI",
                ),
                VectorSearchProfile(
                    name="myExhaustiveKnnProfile",
                    algorithm_configuration_name="myExhaustiveKnn",
                    vectorizer="myOpenAI",
                ),
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    name="myOpenAI",
                    kind="azureOpenAI",
                    azure_open_ai_parameters=azure_open_ai_parameters,
                ),
            ],
        )

    def get_semantic_search_config(self):
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="content")]
            ),
        )

        # Create the semantic search with the configuration
        return SemanticSearch(configurations=[semantic_config])
