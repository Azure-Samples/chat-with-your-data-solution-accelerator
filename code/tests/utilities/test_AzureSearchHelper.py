import pytest
from unittest.mock import ANY, MagicMock, patch
from backend.batch.utilities.helpers.AzureSearchHelper import AzureSearchHelper

AZURE_AUTH_TYPE = "keys"
AZURE_SEARCH_KEY = "mock-key"
AZURE_SEARCH_SERVICE = "mock-service"
AZURE_SEARCH_INDEX = "mock-index"
AZURE_SEARCH_USE_SEMANTIC_SEARCH = False
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = "default"
AZURE_SEARCH_CONVERSATIONS_LOG_INDEX = "mock-log-index"


@pytest.fixture(autouse=True)
def AzureSearchMock():
    with patch("backend.batch.utilities.helpers.AzureSearchHelper.AzureSearch") as mock:
        yield mock


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.helpers.AzureSearchHelper.LLMHelper") as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = [
            0
        ] * 1536

        yield llm_helper


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.helpers.AzureSearchHelper.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_AUTH_TYPE = AZURE_AUTH_TYPE
        env_helper.AZURE_SEARCH_KEY = AZURE_SEARCH_KEY
        env_helper.AZURE_SEARCH_SERVICE = AZURE_SEARCH_SERVICE
        env_helper.AZURE_SEARCH_INDEX = AZURE_SEARCH_INDEX
        env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH = AZURE_SEARCH_USE_SEMANTIC_SEARCH
        env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = (
            AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
        )
        env_helper.AZURE_SEARCH_CONVERSATIONS_LOG_INDEX = (
            AZURE_SEARCH_CONVERSATIONS_LOG_INDEX
        )

        yield env_helper


def test_get_vector_store_keys(AzureSearchMock: MagicMock, llm_helper_mock: MagicMock):
    # given
    azure_search_helper = AzureSearchHelper()

    # when
    vector_store = azure_search_helper.get_vector_store()

    # then
    assert vector_store == AzureSearchMock.return_value

    AzureSearchMock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=AZURE_SEARCH_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        search_type="hybrid",
        semantic_configuration_name=AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
        user_agent="langchain chatwithyourdata-sa",
    )


def test_get_vector_store_rbac(
    AzureSearchMock: MagicMock, llm_helper_mock: MagicMock, env_helper_mock: MagicMock
):
    # given
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_helper = AzureSearchHelper()

    # when
    vector_store = azure_search_helper.get_vector_store()

    # then
    assert vector_store == AzureSearchMock.return_value

    AzureSearchMock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=None,
        index_name=AZURE_SEARCH_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        search_type="hybrid",
        semantic_configuration_name=AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
        user_agent="langchain chatwithyourdata-sa",
    )


def test_get_conversation_logger_keys(
    AzureSearchMock: MagicMock, llm_helper_mock: MagicMock
):
    # given
    azure_search_helper = AzureSearchHelper()

    # when
    conversation_logger = azure_search_helper.get_conversation_logger()

    # then
    assert conversation_logger == AzureSearchMock.return_value

    AzureSearchMock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        user_agent="langchain chatwithyourdata-sa",
    )


def test_get_conversation_logger_rbac(
    AzureSearchMock: MagicMock, llm_helper_mock: MagicMock, env_helper_mock: MagicMock
):
    # given
    env_helper_mock.AZURE_AUTH_TYPE = "rbac"
    azure_search_helper = AzureSearchHelper()

    # when
    conversation_logger = azure_search_helper.get_conversation_logger()

    # then
    assert conversation_logger == AzureSearchMock.return_value

    AzureSearchMock.assert_called_once_with(
        azure_search_endpoint=AZURE_SEARCH_SERVICE,
        azure_search_key=None,
        index_name=AZURE_SEARCH_CONVERSATIONS_LOG_INDEX,
        embedding_function=llm_helper_mock.get_embedding_model.return_value.embed_query,
        fields=ANY,
        user_agent="langchain chatwithyourdata-sa",
    )
