import pytest
import requests
from pytest_httpserver import HTTPServer
from tests.constants import (
    COMPUTER_VISION_VECTORIZE_TEXT_PATH,
    COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
)
from tests.functional.app_config import AppConfig
from tests.request_matching import RequestMatcher, verify_request_made

pytestmark = pytest.mark.functional

path = "/api/conversation"
body = {
    "conversation_id": "123",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
        {"role": "user", "content": "What is the meaning of life?"},
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
                    "finish_reason": "function_call",
                    "index": 0,
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "function_call": {
                            "arguments": '{"question":"What is the meaning of life?"}',
                            "name": "search_documents",
                        },
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
                        "content": "42 is the meaning of life[doc1].",
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
                        "content": r'{"citations": [{"content": "[/documents/doc.pdf](https://source)\n\n\ncontent", "id": "doc_1", "chunk_id": 95, "title": "/documents/doc.pdf", "filepath": "source", "url": "[/documents/doc.pdf](https://source)", "metadata": {"offset": 202738, "source": "https://source", "markdown_url": "[/documents/doc.pdf](https://source)", "title": "/documents/doc.pdf", "original_url": "https://source", "chunk": 95, "key": "doc_1", "filename": "source"}}], "intent": "What is the meaning of life?"}',
                        "end_turn": False,
                        "role": "tool",
                    },
                    {
                        "content": "42 is the meaning of life[doc1].",
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


def test_text_passed_to_computer_vision_to_generate_text_embeddings(
    app_url: str, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        httpserver,
        RequestMatcher(
            path=COMPUTER_VISION_VECTORIZE_TEXT_PATH,
            method=COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
            json={
                "text": "What is the meaning of life?",
            },
            query_string="api-version=2024-02-01&model-version=2023-04-15",
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": app_config.get(
                    "AZURE_COMPUTER_VISION_KEY"
                ),
            },
            times=1,
        ),
    )
