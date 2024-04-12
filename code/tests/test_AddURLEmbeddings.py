import sys
import os
from unittest.mock import patch
import azure.functions as func


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.AddURLEmbeddings import do_add_url_embeddings  # noqa: E402


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
@patch("backend.batch.AddURLEmbeddings.EnvHelper")
def test_add_url_embeddings_when_url_set_in_body(mock_env_helper, _, __):
    mock_env_helper.return_value.LOGLEVEL = "INFO"

    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )

    response = do_add_url_embeddings(fake_request)

    assert response.status_code == 200


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
@patch("backend.batch.AddURLEmbeddings.EnvHelper")
def test_add_url_embeddings_when_url_set_in_param(mock_env_helper, _, __):
    mock_env_helper.return_value.LOGLEVEL = "INFO"

    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        headers={"Content-Type": "application/json"},
        params={"url": "https://example.com"},
    )

    response = do_add_url_embeddings(fake_request)

    assert response.status_code == 200


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
@patch("backend.batch.AddURLEmbeddings.EnvHelper")
def test_add_url_embeddings_returns_400_when_url_not_set(mock_env_helper, _, __):
    mock_env_helper.return_value.LOGLEVEL = "INFO"

    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        params={},
    )

    response = do_add_url_embeddings(fake_request)

    assert response.status_code == 400
