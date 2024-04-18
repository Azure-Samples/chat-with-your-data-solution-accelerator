import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.AzureSearchIVDatasourceHelper import (
    AzureSearchIVDatasourceHelper,
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
        "backend.batch.utilities.helpers.AzureSearchIVDatasourceHelper.EnvHelper"
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
        "backend.batch.utilities.helpers.AzureSearchIVDatasourceHelper.SearchIndexerClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_data_container_mock():
    with patch(
        "backend.batch.utilities.helpers.AzureSearchIVDatasourceHelper.SearchIndexerDataContainer"
    ) as mock:
        yield mock


def test_create_or_update_datasource_keys(
    search_indexer_client_mock: MagicMock,
    search_indexer_data_container_mock: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    azure_search_iv_datasource_helper = AzureSearchIVDatasourceHelper(env_helper_mock)

    # when
    azure_search_iv_datasource_helper.create_or_update_datasource()

    # then

    assert (
        azure_search_iv_datasource_helper.indexer_client
        == search_indexer_client_mock.return_value
    )
    search_indexer_data_container_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_BLOB_CONTAINER_NAME
    )


def test_create_or_update_datasource_rbac(
    search_indexer_client_mock: MagicMock,
    search_indexer_data_container_mock: MagicMock,
    env_helper_mock: MagicMock,
):
    # given
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_iv_datasource_helper = AzureSearchIVDatasourceHelper(env_helper_mock)

    # when
    azure_search_iv_datasource_helper.create_or_update_datasource()

    # then

    assert (
        azure_search_iv_datasource_helper.indexer_client
        == search_indexer_client_mock.return_value
    )
    search_indexer_data_container_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_BLOB_CONTAINER_NAME
    )
