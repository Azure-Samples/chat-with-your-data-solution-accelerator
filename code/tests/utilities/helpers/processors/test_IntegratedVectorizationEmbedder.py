import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder import (
    IntegratedVectorizationEmbedder,
)
from backend.batch.utilities.document_chunking.ChunkingStrategy import ChunkingSettings
from backend.batch.utilities.document_loading import LoadingSettings
from backend.batch.utilities.document_loading.Strategies import LoadingStrategy

AZURE_SEARCH_INDEXER_NAME = "mock-indexer-name"
CHUNKING_SETTINGS = ChunkingSettings({"strategy": "layout", "size": 1, "overlap": 0})
LOADING_SETTINGS = LoadingSettings({"strategy": LoadingStrategy.LAYOUT})


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_SEARCH_INDEXER_NAME = AZURE_SEARCH_INDEXER_NAME

        yield env_helper


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value
        llm_helper.get_embedding_model.return_value.embed_query.return_value = [
            0
        ] * 1536
        llm_helper.generate_embeddings.return_value = [123]
        yield llm_helper


@pytest.fixture(autouse=True)
def azure_search_iv_index_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.AzureSearchIndex"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_datasource_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.AzureSearchDatasource"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_skillset_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.AzureSearchSkillset"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_indexer_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.AzureSearchIndexer"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_config_helper():
    with patch(
        "backend.batch.utilities.helpers.embedders.IntegratedVectorizationEmbedder.ConfigHelper"
    ) as mock:
        config_helper = mock.get_active_config_or_default
        iv_config = config_helper.return_value.integrated_vectorization_config
        yield iv_config


def test_process_using_integrated_vectorization(
    env_helper_mock: MagicMock,
    llm_helper_mock: MagicMock,
    azure_search_iv_index_helper_mock: MagicMock,
    azure_search_iv_datasource_helper_mock: MagicMock,
    azure_search_iv_skillset_helper_mock: MagicMock,
    azure_search_iv_indexer_helper_mock: MagicMock,
    mock_config_helper,
):
    # given
    document_processor = IntegratedVectorizationEmbedder(env_helper_mock)
    source_url = "https://dagrs.berkeley.edu/sites/default/files/2020-01/sample.pdf"

    # when
    result = document_processor.process_using_integrated_vectorization(source_url)

    # then
    azure_search_iv_datasource_helper_mock.assert_called_once_with(env_helper_mock)
    azure_search_iv_datasource_helper_mock.return_value.create_or_update_datasource.assert_called_once()

    azure_search_iv_index_helper_mock.assert_called_once_with(
        env_helper_mock, llm_helper_mock
    )
    azure_search_iv_index_helper_mock.return_value.create_or_update_index.assert_called_once()

    azure_search_iv_skillset_helper_mock.assert_called_once_with(
        env_helper_mock, mock_config_helper
    )
    azure_search_iv_skillset_helper_mock.return_value.create_skillset.assert_called_once()

    azure_search_iv_indexer_helper_mock.assert_called_once_with(env_helper_mock)
    azure_search_iv_indexer_helper_mock.return_value.create_or_update_indexer.assert_called_once()

    assert (
        result
        == azure_search_iv_indexer_helper_mock.return_value.create_or_update_indexer.return_value
    )
    assert (
        azure_search_iv_skillset_helper_mock.return_value.create_skillset.return_value.skills
        is not None
    )
