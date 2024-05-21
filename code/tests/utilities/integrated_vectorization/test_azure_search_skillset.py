import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.integrated_vectorization.azure_search_skillset import (
    AzureSearchSkillset,
)
from azure.search.documents.indexes.models import (
    SearchIndexerSkillset,
    SplitSkill,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerIndexProjections,
)

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"
AZURE_OPENAI_ENDPOINT = "mock-openai-endpoint"
AZURE_OPENAI_EMBEDDING_MODEL = "mock-openai-embedding-model"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_skillset.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX
        env_helper.AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT
        env_helper.AZURE_OPENAI_EMBEDDING_MODEL = AZURE_OPENAI_EMBEDDING_MODEL

        yield env_helper


@pytest.fixture(autouse=True)
def search_indexer_client_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_skillset.SearchIndexerClient"
    ) as mock:
        indexer_client = mock.return_value
        indexer_client.create_or_update_skillset.return_value = SearchIndexerSkillset(
            name="skillset_name",
            description="Skillset to chunk documents and generating embeddings",
            skills=[SplitSkill, AzureOpenAIEmbeddingSkill],
            index_projections=SearchIndexerIndexProjections,
        )
        yield mock


def test_create_skillset_keys(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
):
    # given
    config = MagicMock()
    azure_search_iv_skillset_helper = AzureSearchSkillset(env_helper_mock, config)

    # when
    create_or_update_skillset = azure_search_iv_skillset_helper.create_skillset()

    # then
    assert create_or_update_skillset.name == "skillset_name"
    assert len(create_or_update_skillset.skills) == 2
    assert create_or_update_skillset.index_projections is not None
    search_indexer_client_mock.return_value.create_or_update_skillset.assert_called_once()


def test_create_skillset_rbac(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
):
    # given
    config = MagicMock()
    env_helper_mock.is_auth_type_keys.return_value = False
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_iv_skillset_helper = AzureSearchSkillset(env_helper_mock, config)

    # when
    create_or_update_skillset = azure_search_iv_skillset_helper.create_skillset()

    # then
    assert create_or_update_skillset.name == "skillset_name"
    assert len(create_or_update_skillset.skills) == 2
    assert create_or_update_skillset.index_projections is not None
    search_indexer_client_mock.return_value.create_or_update_skillset.assert_called_once()
