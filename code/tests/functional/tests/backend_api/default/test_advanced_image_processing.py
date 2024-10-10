import json
import re
from unittest.mock import ANY
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
        f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_MODEL_INFO','model')}/chat/completions",
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
            "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
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
        re.compile(
            f"/openai/deployments/({app_config.get_from_json('AZURE_OPENAI_MODEL_INFO','model')}|{app_config.get('AZURE_OPENAI_VISION_MODEL')})/chat/completions"
        ),
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
            "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
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

    httpserver.expect_oneshot_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')/docs/search.post.search",
        method="POST",
    ).respond_with_json(
        {
            "value": [
                {
                    "@search.score": 0.02916666865348816,
                    "id": "doc_1",
                    "content": "content",
                    "content_vector": [
                        -0.012909674,
                        0.00838491,
                    ],
                    "metadata": '{"id": "doc_1", "source": "https://source_SAS_TOKEN_PLACEHOLDER_", "title": "/documents/doc.png", "chunk": 95, "offset": 202738, "page_number": null}',
                    "title": "/documents/doc.png",
                    "source": "https://source_SAS_TOKEN_PLACEHOLDER_",
                    "chunk": 95,
                    "offset": 202738,
                }
            ]
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
                        "content": ANY,  # SAS URL changes each time
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
        "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
        "object": "response.object",
    }
    assert response.headers["Content-Type"] == "application/json"

    content = json.loads(response.json()["choices"][0]["messages"][0]["content"])

    assert content == {
        "citations": [
            {
                "content": ANY,
                "id": "doc_1",
                "chunk_id": 95,
                "title": "/documents/doc.png",
                "filepath": "source",
                "url": ANY,
                "metadata": {
                    "offset": 202738,
                    "source": "https://source_SAS_TOKEN_PLACEHOLDER_",
                    "markdown_url": ANY,
                    "title": "/documents/doc.png",
                    "original_url": "https://source_SAS_TOKEN_PLACEHOLDER_",
                    "chunk": 95,
                    "key": "doc_1",
                    "filename": "source",
                },
            }
        ],
        "intent": "What is the meaning of life?",
    }


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


def test_image_urls_included_in_call_to_openai(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    request = verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_VISION_MODEL')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "content": "system prompt",
                        "role": "system",
                    },
                    {
                        "content": '## Retrieved Documents\n{"retrieved_documents":[{"[doc1]":{"content":"content"}}]}\n\n## User Question\nUse the Retrieved Documents to answer the question: user question',
                        "name": "example_user",
                        "role": "system",
                    },
                    {
                        "content": "answer",
                        "name": "example_assistant",
                        "role": "system",
                    },
                    {
                        "content": "You are an AI assistant that helps people find information.",
                        "role": "system",
                    },
                    {"content": "Hello", "role": "user"},
                    {"content": "Hi, how can I help?", "role": "assistant"},
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": '## Retrieved Documents\n{"retrieved_documents":[{"[doc1]":{"content":"content"}}]}\n\n## User Question\nUse the Retrieved Documents to answer the question: What is the meaning of life?',
                            },
                            {"type": "image_url", "image_url": {"url": ANY}},
                        ],
                        "role": "user",
                    },
                ],
                "model": app_config.get("AZURE_OPENAI_VISION_MODEL"),
                "max_tokens": int(app_config.get("AZURE_OPENAI_MAX_TOKENS")),
                "temperature": 0,
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
    )[0]

    assert request.json["messages"][6]["content"][1]["image_url"]["url"].startswith(
        "https://source"
    )
