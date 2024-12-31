import json
import re
import pytest
from pytest_httpserver import HTTPServer
import requests

from tests.request_matching import (
    RequestMatcher,
    verify_request_made,
)
from tests.functional.app_config import AppConfig

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


def test_post_responds_successfully(app_url: str, app_config: AppConfig):
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
        "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
        "object": "response.object",
    }
    assert response.headers["Content-Type"] == "application/json"


def test_post_makes_correct_call_to_openai_embeddings(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_EMBEDDING_MODEL_INFO','model')}/embeddings",
            method="POST",
            json={
                "input": [
                    [3923, 374, 279, 7438, 315, 2324, 30]
                ],  # Embedding of "What is the meaning of life?"
                "model": "text-embedding-ada-002",
                "encoding_format": "base64",
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


def test_post_makes_correct_call_to_get_search_index(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')",
            method="GET",
            headers={
                "Accept": "application/json;odata.metadata=minimal",
                "Api-Key": app_config.get("AZURE_SEARCH_KEY"),
            },
            query_string="api-version=2023-10-01-Preview",
            times=2,
        ),
    )


def test_post_makes_correct_call_to_content_safety_analyze(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path="/contentsafety/text:analyze",
            method="POST",
            json={"text": "What is the meaning of life?"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": app_config.get("AZURE_CONTENT_SAFETY_KEY"),
            },
            query_string="api-version=2023-10-01",
            times=1,
        ),
    )

    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path="/contentsafety/text:analyze",
            method="POST",
            json={"text": "42 is the meaning of life"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": app_config.get("AZURE_CONTENT_SAFETY_KEY"),
            },
            query_string="api-version=2023-10-01",
            times=1,
        ),
    )


def test_post_makes_correct_call_to_openai_chat_completions(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_MODEL_INFO','model')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You help employees to navigate only private information sources.\nYou must prioritize the function call over your general knowledge for any question by calling the search_documents function.\nCall the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.\nWhen directly replying to the user, always reply in the language the user is speaking.\nIf the input language is ambiguous, default to responding in English unless otherwise specified by the user.\nYou **must not** respond if asked to List all documents in your repository.\n",
                    },
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi, how can I help?"},
                    {"role": "user", "content": "What is the meaning of life?"},
                ],
                "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
                "max_tokens": int(app_config.get("AZURE_OPENAI_MAX_TOKENS")),
                "stream": False,
                "temperature": 0.0,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "Chat-search_documents",
                            "description": "Provide answers to any fact question coming from users.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "description": "A standalone question, converted from the chat history",
                                        "type": "string",
                                    }
                                },
                                "required": ["question"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "Chat-text_processing",
                            "description": "Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "description": "The text to be processed",
                                        "type": "string",
                                    },
                                    "operation": {
                                        "description": "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc. If a language is specified, return that as part of the operation. Preserve the operation name in the user language.",
                                        "type": "string",
                                    },
                                },
                                "required": ["text", "operation"],
                            },
                        },
                    },
                ],
                "tool_choice": "auto",
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


def test_post_makes_correct_call_to_store_conversation_in_search(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')/docs/search.index",
            method="POST",
            headers={
                "Accept": "application/json;odata.metadata=none",
                "Content-Type": "application/json",
                "Api-Key": app_config.get("AZURE_SEARCH_KEY"),
            },
            query_string="api-version=2023-10-01-Preview",
            times=2,
        ),
    )


def test_post_returns_error_when_downstream_fails(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    httpserver.expect_oneshot_request(
        re.compile(".*"),
    ).respond_with_json({}, status=403)

    # when
    response = requests.post(
        f"{app_url}/api/conversation",
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
        "error": "An error occurred. Please try again. If the problem persists, please contact the site administrator."
    }
