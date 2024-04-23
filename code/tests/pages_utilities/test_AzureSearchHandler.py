import pytest
from unittest.mock import Mock, patch
from backend.pages.utilities.AzureSearchHandler import AzureSearchHandler
import json


@pytest.fixture
def env_helper_mock():
    mock = Mock()
    mock.AZURE_SEARCH_SERVICE = "https://example.search.windows.net"
    mock.AZURE_SEARCH_INDEX = "example-index"
    mock.AZURE_SEARCH_KEY = "example-key"
    mock.is_auth_type_keys = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_azure_search_helper():
    with patch("backend.pages.utilities.AzureSearchHandler.AzureSearchHelper") as mock:
        vector_store = mock.return_value.get_vector_store.return_value.client
        yield vector_store


@pytest.fixture
def handler(env_helper_mock, mock_azure_search_helper):
    with patch(
        "backend.pages.utilities.AzureSearchHandler.AzureSearchHelper",
        return_value=mock_azure_search_helper,
    ):
        return AzureSearchHandler(env_helper_mock)


def test_create_search_client(handler, mock_azure_search_helper):
    # when
    search_client = handler.create_search_client()

    # then
    assert search_client == mock_azure_search_helper


def test_process_results(handler):
    # given
    results = [{"metadata": json.dumps({"chunk": 1}), "content": "Content 1"}]

    # when
    df = handler.process_results(results)

    # then
    assert df.iloc[0]["Chunk"] == 1
    assert df.iloc[0]["Content"] == "Content 1"


def test_delete_files(handler):
    # given
    files = {"file1": ["1", "2"]}
    with patch(
        "backend.pages.utilities.AzureSearchHandler.st.session_state", {"file1": True}
    ), patch("backend.pages.utilities.AzureSearchHandler.st.info") as mock_info, patch(
        "backend.pages.utilities.AzureSearchHandler.st.success"
    ) as mock_success, patch(
        "backend.pages.utilities.AzureSearchHandler.st.stop"
    ) as mock_stop:

        # when
        handler.delete_files(files)

        # then
        mock_success.assert_called_once_with("Deleted files: ['file1']")
        assert not mock_info.called
        assert not mock_stop.called
