import json
import pytest
from pytest_httpserver import HTTPServer
import requests

from tests.functional.backend_api.app_config import AppConfig

pytestmark = pytest.mark.functional


def test_post(app_url: str, app_config: AppConfig):
    # when
    response = requests.post(
        f"{app_url}/api/conversation/custom",
        json={
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
            ],
        },
    )

    # then
    assert response.status_code == 200
    assert json.loads(response.text) == {
        "choices": [
            {
                "messages": [
                    {
                        "content": '{"citations": [], "intent": "What is the meaning of life?"}',
                        "end_turn": False,
                        "role": "tool",
                    },
                    {
                        "content": "42 is the meaning of life",
                        "end_turn": True,
                        "role": "assistant",
                    },
                ]
            }
        ],
        "created": "response.created",
        "id": "response.id",
        "model": app_config.get("AZURE_OPENAI_MODEL"),
        "object": "response.object",
    }
    assert response.headers["Content-Type"] == "application/json"


def test_post_returns_error_when_downstream_fails(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # given
    httpserver.clear_all_handlers()  # Clear default successful responses

    httpserver.expect_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_EMBEDDING_MODEL')}/embeddings",
        method="POST",
    ).respond_with_json({}, status=500)

    # when
    response = requests.post(
        f"{app_url}/api/conversation/custom",
        json={
            "conversation_id": "123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"},
                {"role": "user", "content": "What is the meaning of life?"},
            ],
        },
    )

    # then
    assert response.status_code == 500
    assert response.headers["Content-Type"] == "application/json"
    assert json.loads(response.text) == {
        "error": "Exception in /api/conversation/custom. See log for more details."
    }
