import json
import pytest
from pytest_httpserver import HTTPServer
import requests
from string import Template

from tests.functional.backend_api.request_matching import (
    RequestMatcher,
    verify_request_made,
)
from tests.functional.backend_api.app_config import AppConfig

pytestmark = pytest.mark.functional

path = "/api/conversation/azure_byod"
body = {
    "conversation_id": "123",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
        {"role": "user", "content": "What is the meaning of life?"},
    ],
}


@pytest.fixture(scope="function", autouse=True)
def setup_default_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_data(
        Template(
            """data: {"id":"","object":"","created":0,"model":"","prompt_filter_results":[{"prompt_index":0,"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}}}],"choices":[]}

data: {"id":"chatcmpl-99tA6ZsoSvjQ0tGV3nGBCdBuEg3KJ","object":"chat.completion.chunk","created":1712144022,"model":"$model","choices":[{"finish_reason":null,"index":0,"delta":{"role":"assistant","content":""},"content_filter_results":{},"logprobs":null}],"system_fingerprint":"fp_68a7d165bf"}

data: {"id":"chatcmpl-99tA6ZsoSvjQ0tGV3nGBCdBuEg3KJ","object":"chat.completion.chunk","created":1712144022,"model":"$model","choices":[{"finish_reason":null,"index":0,"delta":{"content":"42 is the meaning of life"},"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}},"logprobs":null}],"system_fingerprint":"fp_68a7d165bf"}

data: {"id":"chatcmpl-99tA6ZsoSvjQ0tGV3nGBCdBuEg3KJ","object":"chat.completion.chunk","created":1712144022,"model":"$model","choices":[{"finish_reason":"stop","index":0,"delta":{"content":null},"content_filter_results":{},"logprobs":null}],"system_fingerprint":"fp_68a7d165bf"}

data: [DONE]
"""
        ).substitute(model=app_config.get("AZURE_OPENAI_MODEL")),
    )

    yield

    httpserver.check()


def test_azure_byod_responds_successfully_when_streaming(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    response = requests.post(f"{app_url}{path}", json=body)

    # then
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json-lines"

    response_lines = response.text.splitlines()
    assert len(response_lines) == 2

    final_response_json = json.loads(response_lines[-1])
    assert final_response_json == {
        "id": "chatcmpl-99tA6ZsoSvjQ0tGV3nGBCdBuEg3KJ",
        "model": app_config.get("AZURE_OPENAI_MODEL"),
        "created": 1712144022,
        "object": "chat.completion.chunk",
        "choices": [
            {
                "messages": [
                    {
                        "content": "42 is the meaning of life",
                        "role": "assistant",
                    },
                ]
            }
        ],
    }


def test_post_makes_correct_call_to_azure_openai(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AI assistant that helps people find information.",
                    },
                ]
                + body["messages"],
                "model": app_config.get("AZURE_OPENAI_MODEL"),
                "temperature": 0.0,
                "max_tokens": 1000,
                "top_p": 1.0,
                "stop": None,
                "stream": True,
            },
            headers={
                "Content-Type": "application/json",
                "api-key": app_config.get("AZURE_OPENAI_API_KEY"),
            },
            query_string="api-version=2024-02-01",
            times=1,
        ),
    )
