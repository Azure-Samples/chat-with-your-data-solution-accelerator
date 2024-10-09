import pytest
from unittest.mock import ANY, MagicMock, patch
from backend.batch.utilities.helpers.azure_search_helper import AzureSearchHelper
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

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"
AZURE_SEARCH_USE_SEMANTIC_SEARCH = False
AZURE_SEARCH_FIELDS_ID = "mock-id"
AZURE_SEARCH_CONTENT_COLUMN = "mock-content"
AZURE_SEARCH_CONTENT_VECTOR_COLUMN = "mock-vector"
AZURE_SEARCH_TITLE_COLUMN = "mock-title"
AZURE_SEARCH_FIELDS_METADATA = "mock-metadata"
AZURE_SEARCH_SOURCE_COLUMN = "mock-source"
AZURE_SEARCH_CHUNK_COLUMN = "mock-chunk"
AZURE_SEARCH_OFFSET_COLUMN = "mock-offset"
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "default"
AZURE_SEARCH_CONVERSATIONS_LOG_INDEX = "mock-log-index"
USE_ADVANCED_IMAGE_PROCESSING = False

SEARCH_EMBEDDINGS = [0, 0, 0, 0]
IMAGE_SEARCH_EMBEDDINGS = [0, 0, 0]


@pytest.fixture(autouse=True)
def azure_search_mock():
    with patch(
        "backend.batch.utilities.helpers.azure_search_helper.AzureSearch"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.helpers.azure_search_helper.LLMHelper") as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = (
            SEARCH_EMBEDDINGS
        )

        yield llm_helper


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.helpers.azure_search_helper.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX
        env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH = AZURE_SEARCH_USE_SEMANTIC_SEARCH
        env_helper.AZURE_SEARCH_FIELDS_ID = AZURE_SEARCH_FIELDS_ID
        env_helper.AZURE_SEARCH_CONTENT_COLUMN = AZURE_SEARCH_CONTENT_COLUMN
        env_helper.AZURE_SEARCH_CONTENT_VECTOR_COLUMN = (
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN
        )
        env_helper.AZURE_SEARCH_TITLE_COLUMN = AZURE_SEARCH_TITLE_COLUMN
        env_helper.AZURE_SEARCH_FIELDS_METADATA = AZURE_SEARCH_FIELDS_METADATA
        env_helper.AZURE_SEARCH_SOURCE_COLUMN = AZURE_SEARCH_SOURCE_COLUMN
        env_helper.AZURE_SEARCH_CHUNK_COLUMN = AZURE_SEARCH_CHUNK_COLUMN
        env_helper.AZURE_SEARCH_OFFSET_COLUMN = AZURE_SEARCH_OFFSET_COLUMN
        env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = (
            AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
        )
        env_helper.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX = (
            AZURE_SEARCH_CONVERSATIONS_LOG_INDEX
        )

        env_helper.USE_ADVANCED_IMAGE_PROCESSING = USE_ADVANCED_IMAGE_PROCESSING
        env_helper.is_auth_type_keys.return_value = True

        yield env_helper


@pytest.fixture(autouse=True)
def reset_search_dimensions():
    AzureSearchHelper._search_dimension = None
    AzureSearchHelper._image_search_dimension = None
    yield
    AzureSearchHelper._search_dimension = None
    AzureSearchHelper._image_search_dimension = None


@pytest.fixture(autouse=True)
def azure_computer_vision_client_mock():
    with patch(
        "backend.batch.utilities.helpers.azure_search_helper.AzureComputerVisionClient"
    ) as mock:
        client = mock.return_value
        client.vectorize_text.return_value = IMAGE_SEARCH_EMBEDDINGS

        yield client


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.AzureKeyCredential")
def test_creates_search_clients_with_keys(
    azure_key_credential_mock: MagicMock,
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
):
    # when
    AzureSearchHelper()

    # then
    azure_key_credential_mock.assert_called_once_with(AZURE_SEARCH_KEY)
    search_client_mock.assert_called_once_with(
        endpoint=AZURE_SEARCH_SERVICE,
        index_name=AZURE_SEARCH_INDEX,
        credential=azure_key_credential_mock.return_value,
    )
    search_index_client_mock.assert_called_once_with(
        endpoint=AZURE_SEARCH_SERVICE, credential=azure_key_credential_mock.return_value
    )


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.DefaultAzureCredential")
def test_creates_search_clients_with_rabc(
    default_azure_credential_mock: MagicMock,
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False

    # when
    AzureSearchHelper()

    # then
    default_azure_credential_mock.assert_called_once_with()
    search_client_mock.assert_called_once_with(
        endpoint=AZURE_SEARCH_SERVICE,
        index_name=AZURE_SEARCH_INDEX,
        credential=default_azure_credential_mock.return_value,
    )
    search_index_client_mock.assert_called_once_with(
        endpoint=AZURE_SEARCH_SERVICE,
        credential=default_azure_credential_mock.return_value,
    )


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_returns_search_client(
    search_index_client_mock: MagicMock, search_client_mock: MagicMock
):
    # given
    azure_search_helper = AzureSearchHelper()

    # when
    search_client = azure_search_helper.get_search_client()

    # then
    assert search_client is search_client_mock.return_value


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_creates_search_index_if_not_exists(
    search_index_client_mock: MagicMock, search_client_mock: MagicMock
):
    # given
    search_index_client_mock.return_value.list_index_names.return_value = [
        "some-irrelevant-index"
    ]

    fields = [
        SimpleField(
            name=AZURE_SEARCH_FIELDS_ID,
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name=AZURE_SEARCH_CONTENT_COLUMN,
            type=SearchFieldDataType.String,
        ),
        SearchField(
            name=AZURE_SEARCH_CONTENT_VECTOR_COLUMN,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=len(SEARCH_EMBEDDINGS),
            vector_search_profile_name="myHnswProfile",
        ),
        SearchableField(
            name=AZURE_SEARCH_FIELDS_METADATA,
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name=AZURE_SEARCH_TITLE_COLUMN,
            type=SearchFieldDataType.String,
            facetable=True,
            filterable=True,
        ),
        SearchableField(
            name=AZURE_SEARCH_SOURCE_COLUMN,
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name=AZURE_SEARCH_CHUNK_COLUMN,
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        SimpleField(
            name=AZURE_SEARCH_OFFSET_COLUMN,
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
    ]

    expected_index = SearchIndex(
        name=AZURE_SEARCH_INDEX,
        fields=fields,
        semantic_search=(
            SemanticSearch(
                configurations=[
                    SemanticConfiguration(
                        name=AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
                        prioritized_fields=SemanticPrioritizedFields(
                            title_field=None,
                            content_fields=[
                                SemanticField(field_name=AZURE_SEARCH_CONTENT_COLUMN)
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

    # when
    AzureSearchHelper().get_search_client()

    # then
    search_index_client_mock.return_value.create_index.assert_called_once_with(
        expected_index
    )


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_creates_search_index_with_image_embeddings_when_advanced_image_processing_enabled(
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.USE_ADVANCED_IMAGE_PROCESSING = True
    search_index_client_mock.return_value.list_index_names.return_value = [
        "some-irrelevant-index"
    ]

    expected_image_vector_field = SearchField(
        name="image_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=len(IMAGE_SEARCH_EMBEDDINGS),
        vector_search_profile_name="myHnswProfile",
    )

    # when
    AzureSearchHelper().get_search_client()

    # then
    search_index_client_mock.return_value.create_index.assert_called_once()
    assert (
        expected_image_vector_field
        in search_index_client_mock.return_value.create_index.call_args.args[0].fields
    )


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_does_not_create_search_index_if_it_exists(
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
):
    # given
    search_index_client_mock.return_value.list_index_names.return_value = [
        AZURE_SEARCH_INDEX
    ]

    # when
    azure_search_helper = AzureSearchHelper()
    azure_search_helper.get_search_client()

    # then
    search_index_client_mock.return_value.create_index.assert_not_called()


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_propogates_exceptions_when_creating_search_index(
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
):
    # given
    expected_exception = Exception()
    search_index_client_mock.return_value.create_index.side_effect = expected_exception

    # when
    with pytest.raises(Exception) as exc_info:
        AzureSearchHelper().get_search_client()

    # then
    assert exc_info.value == expected_exception


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_get_conversation_logger_keys(
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
    azure_search_mock: MagicMock,
    llm_helper_mock: MagicMock,
):
    # given
    azure_search_helper = AzureSearchHelper()

    # when
    conversation_logger = azure_search_helper.get_conversation_logger()

    # then
    assert conversation_logger == azure_search_mock.return_value

    azure_search_mock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        user_agent="langchain chatwithyourdata-sa",
    )


@patch("backend.batch.utilities.helpers.azure_search_helper.SearchClient")
@patch("backend.batch.utilities.helpers.azure_search_helper.SearchIndexClient")
def test_get_conversation_logger_rbac(
    search_index_client_mock: MagicMock,
    search_client_mock: MagicMock,
    azure_search_mock: MagicMock,
    llm_helper_mock: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False
    azure_search_helper = AzureSearchHelper()

    # when
    conversation_logger = azure_search_helper.get_conversation_logger()

    # then
    assert conversation_logger == azure_search_mock.return_value

    azure_search_mock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=None,
        index_name=AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        user_agent="langchain chatwithyourdata-sa",
    )
