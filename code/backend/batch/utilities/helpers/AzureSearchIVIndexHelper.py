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


class AzureSearchIVIndexHelper:
    def __init__(self):
        pass

    def get_iv_search_store(self):
        env_helper: EnvHelper = EnvHelper()
        # Create a search index
        index_client = SearchIndexClient(
            env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )
        fields = [
            SearchField(
                name="parent_id",
                type=SearchFieldDataType.String,
                sortable=True,
                filterable=True,
                facetable=True,
            ),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="metadata", type=SearchFieldDataType.String),
            SearchableField(
                name="source", type=SearchFieldDataType.String, filterable=True
            ),
            SearchField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                sortable=True,
                filterable=True,
                facetable=True,
                analyzer_name="keyword",
            ),
            SimpleField(
                name="chunk",
                type=SearchFieldDataType.String,
                sortable=False,
                filterable=False,
                facetable=False,
            ),
            SearchField(
                name="vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=1536,
                vector_search_profile_name="myHnswProfile",
            ),
            SimpleField(name="offset", type=SearchFieldDataType.Int32, filterable=True),
        ]

        # Configure the vector search configuration
        vector_search = VectorSearch(
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
                    azure_open_ai_parameters=AzureOpenAIParameters(
                        resource_uri=env_helper.AZURE_OPENAI_ENDPOINT,
                        deployment_id=env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
                        api_key=env_helper.OPENAI_API_KEY,
                    ),
                ),
            ],
        )

        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="chunk")]
            ),
        )

        # Create the semantic search with the configuration
        semantic_search = SemanticSearch(configurations=[semantic_config])

        # Create the search index
        index = SearchIndex(
            name=env_helper.AZURE_SEARCH_INDEX,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )
        result = index_client.create_or_update_index(index)
        print(f"{result.name} created")
        return result
