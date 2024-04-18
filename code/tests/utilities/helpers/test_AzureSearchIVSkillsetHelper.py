import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper import (
    AzureSearchIVSkillsetHelper,
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
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.EnvHelper"
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
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.SearchIndexerClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def split_skill_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.SplitSkill"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_open_ai_embedding_skill_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.AzureOpenAIEmbeddingSkill"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_index_projections_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.SearchIndexerIndexProjections"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_skillset_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVSkillsetHelper.SearchIndexerSkillset"
    ) as mock:
        yield mock


def test_create_skillset_keys(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    split_skill_mock: MagicMock,
    azure_open_ai_embedding_skill_mock: MagicMock,
    search_indexer_index_projections_mock: MagicMock,
    search_indexer_skillset_mock: MagicMock,
):
    # given
    azure_search_iv_skillset_helper = AzureSearchIVSkillsetHelper(
        env_helper_mock.return_value
    )

    # when
    create_or_update_skillset = azure_search_iv_skillset_helper.create_skillset()

    # then
    assert create_or_update_skillset == search_indexer_skillset_mock.return_value.name

    search_indexer_skillset_mock.assert_called_once_with(
        name=f"{env_helper_mock.return_value.AZURE_SEARCH_INDEX}-skillset",
        description="Skillset to chunk documents and generating embeddings",
        skills=[
            split_skill_mock.return_value,
            azure_open_ai_embedding_skill_mock.return_value,
        ],
        index_projections=search_indexer_index_projections_mock.return_value,
    )
