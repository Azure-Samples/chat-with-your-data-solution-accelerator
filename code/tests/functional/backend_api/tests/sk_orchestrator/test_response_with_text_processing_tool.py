import pytest
from pytest_httpserver import HTTPServer
import requests

from tests.functional.backend_api.request_matching import (
    RequestMatcher,
    verify_request_made,
)
from tests.functional.backend_api.app_config import AppConfig

pytestmark = pytest.mark.functional

path = "/api/conversation/custom"
body = {
    "conversation_id": "123",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
        {"role": "user", "content": "What is the meaning of life, in uppercase?"},
    ],
}


@pytest.fixture(autouse=True)
def completions_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "choices": [
                {
                    "content_filter_results": {},
                    "finish_reason": "tool_calls",
                    "index": 0,
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": '{"text":"What is the meaning of life?","operation":"Convert to Uppercase"}',
                                    "name": "Chat-text_processing",
                                },
                                "id": "call_9ZgrCHgwHooEPFSoNpH81RBm",
                                "type": "function",
                            }
                        ],
                    },
                }
            ],
            "created": 1714576877,
            "id": "chatcmpl-9K63hMvVH1DyQJqqM7rFE4oRPFCeR",
            "model": app_config.get("AZURE_OPENAI_MODEL"),
            "object": "chat.completion",
            "prompt_filter_results": [
                {
                    "prompt_index": 0,
                    "content_filter_results": {
                        "hate": {"filtered": False, "severity": "safe"},
                        "self_harm": {"filtered": False, "severity": "safe"},
                        "sexual": {"filtered": False, "severity": "safe"},
                        "violence": {"filtered": False, "severity": "safe"},
                    },
                }
            ],
            "system_fingerprint": "fp_2f57f81c11",
            "usage": {
                "completion_tokens": 21,
                "prompt_tokens": 256,
                "total_tokens": 277,
            },
        }
    )

    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "choices": [
                {
                    "content_filter_results": {
                        "hate": {"filtered": False, "severity": "safe"},
                        "self_harm": {"filtered": False, "severity": "safe"},
                        "sexual": {"filtered": False, "severity": "safe"},
                        "violence": {"filtered": False, "severity": "safe"},
                    },
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": "WHAT IS THE MEANING OF LIFE?",
                        "role": "assistant",
                    },
                }
            ],
            "created": 1714576891,
            "id": "chatcmpl-9K63vDGs3slJFynnpi2K6RcVPwgrT",
            "model": app_config.get("AZURE_OPENAI_MODEL"),
            "object": "chat.completion",
            "prompt_filter_results": [
                {
                    "prompt_index": 0,
                    "content_filter_results": {
                        "hate": {"filtered": False, "severity": "safe"},
                        "self_harm": {"filtered": False, "severity": "safe"},
                        "sexual": {"filtered": False, "severity": "safe"},
                        "violence": {"filtered": False, "severity": "safe"},
                    },
                }
            ],
            "system_fingerprint": "fp_2f57f81c11",
            "usage": {
                "completion_tokens": 101,
                "prompt_tokens": 4288,
                "total_tokens": 4389,
            },
        }
    )


def test_post_responds_successfully(app_url: str, app_config: AppConfig):
    # when
    response = requests.post(f"{app_url}{path}", json=body)

    # then
    assert response.status_code == 200
    assert response.json() == {
        "choices": [
            {
                "messages": [
                    {
                        "content": '{"citations": [], "intent": "What is the meaning of life, in uppercase?"}',
                        "end_turn": False,
                        "role": "tool",
                    },
                    {
                        "content": "WHAT IS THE MEANING OF LIFE?",
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


def test_post_makes_correct_call_to_openai_chat_completions_in_text_processing_tool(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "content": "You are an AI assistant for the user.",
                        "role": "system",
                    },
                    {
                        "content": "Convert to Uppercase the following TEXT: What is the meaning of life?",
                        "role": "user",
                    },
                ],
                "model": app_config.get("AZURE_OPENAI_MODEL"),
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {app_config.get('AZURE_OPENAI_API_KEY')}",
                "Api-Key": app_config.get("AZURE_OPENAI_API_KEY"),
            },
            query_string="api-version=2024-02-01",
            times=1,
        ),
    )


def test_post_does_not_call_azure_search(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')/docs/search.post.search",
            method="POST",
            times=0,
        ),
    )
