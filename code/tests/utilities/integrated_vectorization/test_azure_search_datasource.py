import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.integrated_vectorization.azure_search_datasource import (
    AzureSearchDatasource,
)
from azure.search.documents.indexes._generated.models import (
    NativeBlobSoftDeleteDeletionDetectionPolicy,
)

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"
AZURE_OPENAI_ENDPOINT = "mock-openai-endpoint"
AZURE_OPENAI_EMBEDDING_MODEL = "mock-openai-embedding-model"
AZURE_SEARCH_DATASOURCE_NAME = "mock-datasource"
AZURE_BLOB_ACCOUNT_NAME = "mock-account-name"
AZURE_BLOB_ACCOUNT_KEY = "mock-key"
AZURE_SUBSCRIPTION_ID = "mock-subscriptionid"
AZURE_RESOURCE_GROUP = "mock-resource-group"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_datasource.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX
        env_helper.AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT
        env_helper.AZURE_OPENAI_EMBEDDING_MODEL = AZURE_OPENAI_EMBEDDING_MODEL
        env_helper.AZURE_SEARCH_DATASOURCE_NAME = AZURE_SEARCH_DATASOURCE_NAME

        yield env_helper


@pytest.fixture(autouse=True)
def search_indexer_client_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_datasource.SearchIndexerClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_data_container_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_datasource.SearchIndexerDataContainer"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def search_indexer_datasource_connection_mock():
    with patch(
        "backend.batch.utilities.integrated_vectorization.azure_search_datasource.SearchIndexerDataSourceConnection"
    ) as mock:
        yield mock


def test_create_or_update_datasource_keys(
    search_indexer_client_mock: MagicMock,
    search_indexer_data_container_mock: MagicMock,
    env_helper_mock: MagicMock,
    search_indexer_datasource_connection_mock: MagicMock,
):
    # given
    azure_search_iv_datasource_helper = AzureSearchDatasource(env_helper_mock)
    keys_datasource_connection = f"DefaultEndpointsProtocol=https;AccountName={env_helper_mock.AZURE_BLOB_ACCOUNT_NAME};AccountKey={env_helper_mock.AZURE_BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net"

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
    search_indexer_datasource_connection_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_SEARCH_DATASOURCE_NAME,
        type="azureblob",
        connection_string=keys_datasource_connection,
        container=search_indexer_data_container_mock.return_value,
        data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
    )


def test_create_or_update_datasource_rbac(
    search_indexer_client_mock: MagicMock,
    search_indexer_data_container_mock: MagicMock,
    env_helper_mock: MagicMock,
    search_indexer_datasource_connection_mock: MagicMock,
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    rbac_datasource_connection = f"ResourceId=/subscriptions/{env_helper_mock.AZURE_SUBSCRIPTION_ID}/resourceGroups/{env_helper_mock.AZURE_RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/{env_helper_mock.AZURE_BLOB_ACCOUNT_NAME}/;"

    azure_search_iv_datasource_helper = AzureSearchDatasource(env_helper_mock)

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
    search_indexer_datasource_connection_mock.assert_called_once_with(
        name=env_helper_mock.AZURE_SEARCH_DATASOURCE_NAME,
        type="azureblob",
        connection_string=rbac_datasource_connection,
        container=search_indexer_data_container_mock.return_value,
        data_deletion_detection_policy=NativeBlobSoftDeleteDeletionDetectionPolicy(),
    )
