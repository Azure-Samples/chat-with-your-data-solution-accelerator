import pytest
from unittest.mock import Mock, patch
from backend.pages.utilities.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)


@pytest.fixture
def env_helper_mock():
    mock = Mock()
    mock.AZURE_SEARCH_SERVICE = "https://example.search.windows.net"
    mock.AZURE_SEARCH_INDEX = "example-index"
    mock.AZURE_SEARCH_KEY = "example-key"
    mock.is_auth_type_keys = Mock(return_value=True)
    return mock


@pytest.fixture
def search_client_mock():
    with patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.SearchClient"
    ) as mock:
        yield mock


@pytest.fixture
def handler(env_helper_mock, search_client_mock):
    with patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.SearchClient",
        return_value=search_client_mock,
    ):
        return IntegratedVectorizationSearchHandler(env_helper_mock)


def test_create_search_client(handler, search_client_mock):
    assert handler.create_search_client() == search_client_mock.return_value


def test_perform_search(handler, search_client_mock):
    # given
    filename = "testfile"

    # when
    handler.perform_search(filename)

    # then
    search_client_mock.search.assert_called_once_with(
        search_text="*",
        select=["id", "chunk_id", "content"],
        filter=f"title eq '{filename}'",
    )


def test_process_results(handler):
    # given
    results = [{"chunk_id": "123_chunk", "content": "some content"}]

    # when
    df = handler.process_results(results)

    # then
    assert df.iloc[0]["Chunk"] == "123"
    assert df.iloc[0]["Content"] == "some content"


def test_delete_files(handler):
    # given
    files = {"file1": ["1", "2"]}
    with patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.st.session_state",
        {"file1": True},
    ), patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.st.info"
    ) as mock_info, patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.st.success"
    ) as mock_success, patch(
        "backend.pages.utilities.IntegratedVectorizationSearchHandler.st.stop"
    ) as mock_stop:

        # when
        handler.delete_files(files)

        # then
        mock_success.assert_called_once_with("Deleted files: ['file1']")
        assert not mock_info.called
        assert not mock_stop.called
