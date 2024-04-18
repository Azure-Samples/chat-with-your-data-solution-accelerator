import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.AzureSearchIVIndexerHelper import (
    AzureSearchIVIndexerHelper,
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
def search_indexer_client_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexerHelper.SearchIndexerClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVIndexerHelper.SearchIndexer"
    ) as mock:
        yield mock


def test_create_or_update_indexer_keys(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    azure_search_indexer = AzureSearchIVIndexerHelper(env_helper_mock)

    # when
    azure_search_indexer.create_or_update_indexer("indexer_name", "skillset_name")

    # then
    azure_search_indexer.indexer_client.create_or_update_indexer.assert_called_once_with(
        search_indexer_mock.return_value
    )


def test_create_or_update_indexer_rbac(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_indexer = AzureSearchIVIndexerHelper(env_helper_mock)

    # when
    azure_search_indexer.create_or_update_indexer("indexer_name", "skillset_name")

    # then
    azure_search_indexer.indexer_client.create_or_update_indexer.assert_called_once_with(
        search_indexer_mock.return_value
    )
