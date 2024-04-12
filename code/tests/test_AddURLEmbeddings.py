import sys
import os
from unittest.mock import patch
import azure.functions as func


sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.AddURLEmbeddings import add_url_embeddings  # noqa: E402


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
def test_add_url_embeddings_when_url_set_in_body(_, __):
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b'{"url": "https://example.com"}',
        headers={"Content-Type": "application/json"},
    )

    response = add_url_embeddings.build().get_user_function()(fake_request)

    assert response.status_code == 200


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
def test_add_url_embeddings_when_url_set_in_param(_, __):
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        headers={"Content-Type": "application/json"},
        params={"url": "https://example.com"},
    )

    response = add_url_embeddings.build().get_user_function()(fake_request)

    assert response.status_code == 200


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
def test_add_url_embeddings_returns_400_when_url_not_set(_, __):
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        params={},
    )

    response = add_url_embeddings.build().get_user_function()(fake_request)

    assert response.status_code == 400
