import sys
import os
from unittest.mock import ANY, MagicMock, patch
import azure.functions as func


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.add_url_embeddings import add_url_embeddings  # noqa: E402


@patch("backend.batch.add_url_embeddings.EmbedderFactory")
def test_add_url_embeddings(mock_embedder_factory: MagicMock):
    # given
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )
    mock_embedder_instance = mock_embedder_factory.create.return_value

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 200
    mock_embedder_instance.embed_file.assert_called_once_with(
        "https://example.com", ".url"
    )


def test_add_url_embeddings_returns_400_when_url_not_set():
    # given
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        params={},
    )

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 400


@patch("backend.batch.add_url_embeddings.EmbedderFactory")
def test_add_url_embeddings_returns_500_when_exception_occurs(
    mock_embedder_factory: MagicMock,
):
    # given
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )
    mock_embedder_instance = mock_embedder_factory.create.return_value
    mock_embedder_instance.embed_file.side_effect = Exception("Test exception")

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 500
    assert (
        b"Unexpected error occurred while processing the contents of the URL https://example.com"
        in response.get_body()
    )


@patch("backend.batch.add_url_embeddings.EnvHelper")
@patch("backend.batch.add_url_embeddings.AzureBlobStorageClient")
@patch("backend.batch.add_url_embeddings.requests")
def test_add_url_embeddings_integrated_vectorization(
    mock_requests: MagicMock,
    mock_blob_storage_client: MagicMock,
    mock_env_helper: MagicMock,
):
    # given
    url = "https://example.com"
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url":"' + url.encode("utf-8") + b'"}',
        headers={"Content-Type": "application/json"},
    )
    mock_env_helper_instance = mock_env_helper.return_value
    mock_env_helper_instance.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True

    mock_get = mock_requests.get
    mock_get.return_value.content = "url data"

    mock_blob_storage_client_instance = mock_blob_storage_client.return_value

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 200
    mock_blob_storage_client_instance.upload_file.assert_called_once_with(
        ANY, url, metadata={"title": url}
    )


@patch("backend.batch.add_url_embeddings.EnvHelper")
@patch("backend.batch.add_url_embeddings.AzureBlobStorageClient")
@patch("backend.batch.add_url_embeddings.requests")
def test_add_url_embeddings_integrated_vectorization_returns_500_when_exception_occurs(
    mock_requests: MagicMock,
    mock_blob_storage_client: MagicMock,
    mock_env_helper: MagicMock,
):
    # given
    url = "https://example.com"
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url":"' + url.encode("utf-8") + b'"}',
        headers={"Content-Type": "application/json"},
    )
    mock_env_helper_instance = mock_env_helper.return_value
    mock_env_helper_instance.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION = True

    mock_get = mock_requests.get
    mock_get.return_value.content = "url data"

    mock_blob_storage_client_instance = mock_blob_storage_client.return_value
    mock_blob_storage_client_instance.upload_file.side_effect = Exception(
        "Test exception"
    )

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 500
    assert (
        b"Error occurred while adding https://example.com to the knowledge base."
        in response.get_body()
    )
