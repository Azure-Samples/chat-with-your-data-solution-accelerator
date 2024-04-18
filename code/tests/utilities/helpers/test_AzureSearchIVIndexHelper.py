import pytest
from unittest.mock import ANY, MagicMock, patch
from backend.batch.utilities.helpers.AzureSearchIVIndexHelper import (
    AzureSearchIVIndexHelper,
)

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX

        yield env_helper


@pytest.fixture(autouse=True)
def search_index_client_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.SearchIndexClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_index_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.SearchIndex"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def vector_seach_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.VectorSearch"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def semantic_config_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.SemanticConfiguration"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def semantic_search_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexHelper.SemanticSearch"
    ) as mock:
        yield mock


def test_create_or_update_index_keys(
    env_helper_mock: MagicMock,
    search_index_mock: MagicMock,
    vector_seach_mock: MagicMock,
    semantic_search_mock: MagicMock,
):
    # given
    azure_search_iv_index_helper = AzureSearchIVIndexHelper(env_helper_mock)

    # when
    azure_search_iv_index_helper.create_or_update_index()

    # then
    search_index_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_SEARCH_INDEX,
        fields=ANY,
        vector_search=vector_seach_mock.return_value,
        semantic_search=semantic_search_mock.return_value,
    )


def test_create_or_update_index_rbac(
    env_helper_mock: MagicMock,
    search_index_mock: MagicMock,
    vector_seach_mock: MagicMock,
    semantic_search_mock: MagicMock,
):
    # given
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_iv_index_helper = AzureSearchIVIndexHelper(env_helper_mock)

    # when
    azure_search_iv_index_helper.create_or_update_index()

    # then
    search_index_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_SEARCH_INDEX,
        fields=ANY,
        vector_search=vector_seach_mock.return_value,
        semantic_search=semantic_search_mock.return_value,
    )
