import pytest
from unittest.mock import MagicMock, patch
from backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder import (
    IntegratedVectorizationEmbedder,
)
from backend.batch.utilities.document_chunking.chunking_strategy import ChunkingSettings
from backend.batch.utilities.document_loading import LoadingSettings
from backend.batch.utilities.document_loading.strategies import LoadingStrategy

AZURE_SEARCH_INDEXER_NAME = "mock-indexer-name"
CHUNKING_SETTINGS = ChunkingSettings({"strategy": "layout", "size": 1, "overlap": 0})
LOADING_SETTINGS = LoadingSettings({"strategy": LoadingStrategy.LAYOUT})


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.AZURE_SEARCH_INDEXER_NAME = AZURE_SEARCH_INDEXER_NAME

        yield env_helper


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.LLMHelper"
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
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.AzureSearchIndex"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_datasource_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.AzureSearchDatasource"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_skillset_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.AzureSearchSkillset"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def azure_search_iv_indexer_helper_mock():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.AzureSearchIndexer"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_config_helper():
    with patch(
        "backend.batch.utilities.helpers.embedders.integrated_vectorization_embedder.ConfigHelper"
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


def test_reprocess_all_runs_indexer_when_indexer_exists(
    env_helper_mock: MagicMock,
    llm_helper_mock: MagicMock,
    azure_search_iv_index_helper_mock: MagicMock,
    azure_search_iv_datasource_helper_mock: MagicMock,
    azure_search_iv_skillset_helper_mock: MagicMock,
    azure_search_iv_indexer_helper_mock: MagicMock,
    mock_config_helper,
):
    # Given
    azure_search_iv_indexer_helper_mock.indexer_exists.return_value = True
    azure_search_iv_indexer_helper_mock.run_indexer.return_value = "Indexer result"

    # When
    embedder = IntegratedVectorizationEmbedder(env_helper_mock)
    embedder.reprocess_all()

    # Then
    azure_search_iv_indexer_helper_mock.return_value.run_indexer.assert_called_once_with(
        env_helper_mock.AZURE_SEARCH_INDEXER_NAME
    )
    azure_search_iv_indexer_helper_mock.return_value.create_or_update_indexer.assert_not_called()


def test_reprocess_all_calls_process_using_integrated_vectorization_when_indexer_does_not_exist(
    env_helper_mock: MagicMock,
    llm_helper_mock: MagicMock,
    azure_search_iv_index_helper_mock: MagicMock,
    azure_search_iv_datasource_helper_mock: MagicMock,
    azure_search_iv_skillset_helper_mock: MagicMock,
    azure_search_iv_indexer_helper_mock: MagicMock,
    mock_config_helper,
):
    # Given
    azure_search_iv_indexer_helper_mock.return_value.indexer_exists.return_value = False

    # When
    embedder = IntegratedVectorizationEmbedder(env_helper_mock)
    embedder.reprocess_all()

    # Then
    azure_search_iv_indexer_helper_mock.return_value.run_indexer.assert_not_called()
    azure_search_iv_indexer_helper_mock.return_value.create_or_update_indexer.assert_called_once()
