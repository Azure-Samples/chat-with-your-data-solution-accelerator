import pytest
from unittest.mock import ANY, MagicMock, patch
from backend.batch.utilities.integrated_vectorization.azure_search_index import (
    AzureSearchIndex,
)
from azure.search.documents.indexes.models import (
    VectorSearch,
    SemanticSearch,
    SearchIndex,
)

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_index.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX

        yield env_helper


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_index.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = [
            0
        ] * 1536

        yield llm_helper


@pytest.fixture(autouse=True)
def search_index_client_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_index.SearchIndexClient"
    ) as mock:
        indexer_client = mock.return_value
        indexer_client.create_or_update_index.return_value = SearchIndex(
            name=AZURE_SEARCH_INDEX,
            fields=ANY,
            vector_search=VectorSearch,
            semantic_search=SemanticSearch,
        )
        yield mock


def test_create_or_update_index_keys(
    env_helper_mock: MagicMock,
    llm_helper_mock: MagicMock,
    search_index_client_mock: MagicMock,
):
    # given
    azure_search_iv_index_helper = AzureSearchIndex(env_helper_mock, llm_helper_mock)

    # when
    result = azure_search_iv_index_helper.create_or_update_index()

    # then
    assert result.name == env_helper_mock.AZURE_SEARCH_INDEX
    assert result.fields == ANY
    assert result.vector_search is not None
    search_index_client_mock.return_value.create_or_update_index.assert_called_once()


def test_create_or_update_index_rbac(
    env_helper_mock: MagicMock,
    llm_helper_mock: MagicMock,
    search_index_client_mock: MagicMock,
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_iv_index_helper = AzureSearchIndex(env_helper_mock, llm_helper_mock)

    # when
    result = azure_search_iv_index_helper.create_or_update_index()

    # then
    assert result.name == env_helper_mock.AZURE_SEARCH_INDEX
    assert result.fields == ANY
    assert result.vector_search is not None
    search_index_client_mock.return_value.create_or_update_index.assert_called_once()
