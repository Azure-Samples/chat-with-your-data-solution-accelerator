import pytest
from unittest.mock import ANY, MagicMock, patch
from backend.batch.utilities.integrated_vectorization.AzureSearchIndexer import (
    AzureSearchIndexer,
)

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.AzureSearchIndexer.EnvHelper"
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
        "backend.batch.utilities.integrated_vectorization.AzureSearchIndexer.SearchIndexerClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.AzureSearchIndexer.SearchIndexer"
    ) as mock:
        yield mock


def test_create_or_update_indexer_keys(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    azure_search_indexer = AzureSearchIndexer(env_helper_mock)

    # when
    azure_search_indexer.create_or_update_indexer("indexer_name", "skillset_name")

    # then
    azure_search_indexer.indexer_client.create_or_update_indexer.assert_called_once_with(
        search_indexer_mock.return_value
    )
    search_indexer_mock.assert_called_once_with(
        name="indexer_name",
        description="Indexer to index documents and generate embeddings",
        skillset_name="skillset_name",
        target_index_name=env_helper_mock.AZURE_SEARCH_INDEX,
        data_source_name=env_helper_mock.AZURE_SEARCH_DATASOURCE_NAME,
        field_mappings=ANY,
    )


def test_create_or_update_indexer_rbac(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_indexer = AzureSearchIndexer(env_helper_mock)

    # when
    azure_search_indexer.create_or_update_indexer("indexer_name", "skillset_name")

    # then
    azure_search_indexer.indexer_client.create_or_update_indexer.assert_called_once_with(
        search_indexer_mock.return_value
    )
    search_indexer_mock.assert_called_once_with(
        name="indexer_name",
        description="Indexer to index documents and generate embeddings",
        skillset_name="skillset_name",
        target_index_name=env_helper_mock.AZURE_SEARCH_INDEX,
        data_source_name=env_helper_mock.AZURE_SEARCH_DATASOURCE_NAME,
        field_mappings=ANY,
    )


def test_reprocess_all_indexer_exists(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    indexer_name = "indexer_name"
    azure_search_indexer = AzureSearchIndexer(env_helper_mock)
    azure_search_indexer.indexer_client.get_indexer_names.return_value = [indexer_name]
    azure_search_indexer.indexer_client.reset_indexer.return_value = None
    azure_search_indexer.indexer_client.run_indexer.return_value = None

    # when
    result = azure_search_indexer.reprocess_all(indexer_name)

    # then
    azure_search_indexer.indexer_client.reset_indexer.assert_called_once_with(
        indexer_name
    )
    azure_search_indexer.indexer_client.run_indexer.assert_called_once_with(
        indexer_name
    )
    assert result == {"status": "success"}


def test_reprocess_all_indexer_not_found(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    indexer_name = "indexer_name"
    azure_search_indexer = AzureSearchIndexer(env_helper_mock)
    azure_search_indexer.indexer_client.get_indexer_names.return_value = [
        "some-indexer"
    ]

    # when
    result = azure_search_indexer.reprocess_all(indexer_name)

    # then
    assert result == {"status": "error"}


def test_reprocess_all_indexer_run_error(
    env_helper_mock: MagicMock,
    search_indexer_client_mock: MagicMock,
    search_indexer_mock: MagicMock,
):
    # given
    indexer_name = "indexer_name"
    azure_search_indexer = AzureSearchIndexer(env_helper_mock)
    azure_search_indexer.indexer_client.get_indexer_names.return_value = [indexer_name]
    azure_search_indexer.indexer_client.run_indexer.return_value = "error"

    # when
    result = azure_search_indexer.reprocess_all(indexer_name)

    # then
    assert result == {"status": "error"}
