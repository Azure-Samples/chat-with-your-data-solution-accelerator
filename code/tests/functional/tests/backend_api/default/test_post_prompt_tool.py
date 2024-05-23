import json
import re

import pytest
import requests
from pytest_httpserver import HTTPServer
from tests.constants import (
    AZURE_STORAGE_CONFIG_CONTAINER_NAME,
    AZURE_STORAGE_CONFIG_FILE_NAME,
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
def setup_config_mocking(httpserver: HTTPServer):
    httpserver.expect_request(
        f"/{AZURE_STORAGE_CONFIG_CONTAINER_NAME}/{AZURE_STORAGE_CONFIG_FILE_NAME}",
        method="GET",
    ).respond_with_json(
        {
            "prompts": {
                "condense_question_prompt": "",
                "answering_system_prompt": "system prompt",
                "answering_user_prompt": "## Retrieved Documents\n{sources}\n\n## User Question\n{question}",
                "use_on_your_data_format": True,
                "post_answering_prompt": "post answering prompt\n{question}\n{answer}\n{sources}",
                "enable_post_answering_prompt": True,
                "enable_content_safety": True,
            },
            "messages": {"post_answering_filter": "post answering filter"},
            "example": {
                "documents": '{"retrieved_documents":[{"[doc1]":{"content":"content"}}]}',
                "user_question": "user question",
                "answer": "answer",
            },
            "document_processors": [],
            "logging": {"log_user_interactions": True, "log_tokens": True},
            "orchestrator": {"strategy": "openai_function"},
            "integrated_vectorization_config": None,
        },
        headers={
            "Content-Type": "application/json",
            "Content-Range": "bytes 0-12882/12883",
        },
    )


@pytest.fixture(autouse=True)
def completions_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": app_config.get("AZURE_OPENAI_MODEL"),
            "usage": {
                "prompt_tokens": 58,
                "completion_tokens": 68,
                "total_tokens": 126,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "function_call": {
                            "name": "search_documents",
                            "arguments": '{"question": "What is the meaning of life?"}',
                        },
                    },
                    "finish_reason": "function_call",
                    "index": 0,
                }
            ],
        }
    )

    httpserver.expect_oneshot_request(
        re.compile(
            f"/openai/deployments/({app_config.get('AZURE_OPENAI_MODEL')}|{app_config.get('AZURE_OPENAI_VISION_MODEL')})/chat/completions"
        ),
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": "gpt-35-turbo",
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 50,
                "total_tokens": 90,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "42 is the meaning of life",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )


def test_post_responds_successfully_when_not_filtered(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # given
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": "gpt-35-turbo",
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 50,
                "total_tokens": 90,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "True",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )

    # when
    response = requests.post(f"{app_url}{path}", json=body)

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


def test_post_responds_successfully_when_filtered(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # given
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": "gpt-35-turbo",
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 50,
                "total_tokens": 90,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "False",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )

    # when
    response = requests.post(f"{app_url}{path}", json=body)

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
                        "content": "post answering filter",
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


def test_post_makes_correct_call_to_openai_from_post_prompt_tool(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # given
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": "gpt-35-turbo",
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 50,
                "total_tokens": 90,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "True",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )

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
                        "content": "post answering prompt\nWhat is the meaning of life?\n42 is the meaning of life\n[doc1]: content",
                        "role": "user",
                    }
                ],
                "model": app_config.get("AZURE_OPENAI_MODEL"),
                "max_tokens": int(app_config.get("AZURE_OPENAI_MAX_TOKENS")),
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
