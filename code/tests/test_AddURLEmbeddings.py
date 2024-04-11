import sys
import os
from unittest.mock import patch
import azure.functions as func


function_app_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../backend/batch")
)
sys.path.append(function_app_path)

from backend.batch.AddURLEmbeddings import do_add_url_embeddings  # noqa: E402


@patch("backend.batch.AddURLEmbeddings.ConfigHelper")
@patch("backend.batch.AddURLEmbeddings.DocumentProcessor")
def test_add_url_embeddings_when_url_set_in_body(_, __):
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
def test_add_url_embeddings_when_url_set_in_param(_, __):
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
def test_add_url_embeddings_returns_400_when_url_not_set(_, __):
    fake_request = func.HttpRequest(
        method="POST",
        url="",
        body=b"",
        params={},
    )

    response = do_add_url_embeddings(fake_request)

    assert response.status_code == 400
