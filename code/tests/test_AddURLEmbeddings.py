import sys
import os
from unittest.mock import ANY, MagicMock, patch
import azure.functions as func


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.AddURLEmbeddings import add_url_embeddings  # noqa: E402


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.EmbedderFactory")
def test_add_url_embeddings(mock_document_processor: MagicMock, _):
    # given
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )
    mock_document_processor_instance = mock_document_processor.return_value

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 200
    mock_document_processor_instance.process.assert_called_once_with(
        source_url="https://example.com", processors=ANY
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


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.EmbedderFactory")
def test_add_url_embeddings_returns_500_when_exception_occurs(
    mock_document_processor: MagicMock, _
):
    # given
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )
    mock_document_processor_instance = mock_document_processor.return_value
    mock_document_processor_instance.process.side_effect = Exception("Test exception")

    # when
    response = add_url_embeddings.build().get_user_function()(fake_request)

    # then
    assert response.status_code == 500
    assert b"Test exception" in response.get_body()


@patch("backend.batch.AddURLEmbeddings.EnvHelper")
@patch("backend.batch.AddURLEmbeddings.AzureBlobStorageClient")
@patch("backend.batch.AddURLEmbeddings.requests")
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


@patch("backend.batch.AddURLEmbeddings.EnvHelper")
@patch("backend.batch.AddURLEmbeddings.AzureBlobStorageClient")
@patch("backend.batch.AddURLEmbeddings.requests")
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
    assert b"Test exception" in response.get_body()
