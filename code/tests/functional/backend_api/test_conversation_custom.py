import json
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
        "model": app_config.get("AZURE_OPENAI_MODEL"),
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
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_EMBEDDING_MODEL')}/embeddings",
            method="POST",
            json={
                "input": [[1199]],
                "model": "text-embedding-ada-002",
                "encoding_format": "base64",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {app_config.get('AZURE_OPENAI_API_KEY')}",
                "Api-Key": app_config.get("AZURE_OPENAI_API_KEY"),
            },
            query_string="api-version=2023-12-01-preview",
            times=2,
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
            query_string="api-version=2023-11-01",
            times=1,
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
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You help employees to navigate only private information sources.\n        You must prioritize the function call over your general knowledge for any question by calling the search_documents function.\n        Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.\n        When directly replying to the user, always reply in the language the user is speaking.\n        ",
                    },
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi, how can I help?"},
                    {"role": "user", "content": "What is the meaning of life?"},
                ],
                "model": "some-openai-model",
                "function_call": "auto",
                "functions": [
                    {
                        "name": "search_documents",
                        "description": "Provide answers to any fact question coming from users.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "A standalone question, converted from the chat history",
                                }
                            },
                            "required": ["question"],
                        },
                    },
                    {
                        "name": "text_processing",
                        "description": "Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "The text to be processed",
                                },
                                "operation": {
                                    "type": "string",
                                    "description": "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc. If a language is specified, return that as part of the operation. Preserve the operation name in the user language.",
                                },
                            },
                            "required": ["text", "operation"],
                        },
                    },
                ],
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {app_config.get('AZURE_OPENAI_API_KEY')}",
                "Api-Key": app_config.get("AZURE_OPENAI_API_KEY"),
            },
            query_string="api-version=2023-12-01-preview",
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
            query_string="api-version=2023-11-01",
            times=2,
        ),
    )


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
