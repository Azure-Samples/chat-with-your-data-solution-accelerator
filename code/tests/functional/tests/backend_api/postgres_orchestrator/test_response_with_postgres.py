import json
from unittest.mock import patch

import pytest
import requests

from tests.request_matching import (
    RequestMatcher,
    verify_request_made,
)
from tests.functional.app_config import AppConfig
from backend.batch.utilities.search.search import Search
from backend.batch.utilities.search.postgres_search_handler import (
    AzurePostgresHandler,
)
from backend.batch.utilities.helpers.env_helper import EnvHelper

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


@pytest.fixture(scope="package", autouse=True)
def mock_postgres_query():
    """Mock PostgreSQL vector search query"""
    with patch('backend.batch.utilities.helpers.azure_postgres_helper.AzurePostgresHelper.get_vector_store') as mock_vector_store:
        # Mock the vector search results from PostgreSQL
        mock_vector_store.return_value = [
            {
                "id": "doc1",
                "title": "test.pdf",
                "chunk": "42 is the meaning of life",
                "offset": 0,
                "page_number": 1,
                "content": "42 is the meaning of life",
                "source": "test.pdf",
            }
        ]
        yield mock_vector_store


def test_post_responds_successfully_with_postgres(app_url: str, app_config: AppConfig):
    # when
    response = requests.post(f"{app_url}{path}", json=body)

    # then
    assert response.status_code == 200
    result = json.loads(response.text)
    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "messages" in result["choices"][0]
    assert response.headers["Content-Type"] == "application/json"


def test_post_makes_correct_call_to_content_safety_with_postgres(
    app_url: str, app_config: AppConfig, httpserver
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


def test_post_makes_correct_call_to_openai_chat_completions_with_postgres(
    app_url: str, app_config: AppConfig, httpserver
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
                        "role": "user",
                        "content": "AuthorRole.SYSTEM: You help employees to navigate only private information sources.\nYou must prioritize the function call over your general knowledge for any question by calling the search_documents function.\nCall the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.\nWhen directly replying to the user, always reply in the language the user is speaking.\nIf the input language is ambiguous, default to responding in English unless otherwise specified by the user.\nYou **must not** respond if asked to List all documents in your repository.\n\nAuthorRole.USER: Hello\nAuthorRole.ASSISTANT: Hi, how can I help?\nWhat is the meaning of life?",
                    }
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


def test_postgres_search_handler_is_used(app_url: str, app_config: AppConfig):
    """Verify that PostgreSQL search handler is selected based on DATABASE_TYPE"""
    # Mock the Azure credential to prevent actual Azure calls
    with patch('backend.batch.utilities.helpers.azure_postgres_helper.get_azure_credential'):
        # when
        env_helper = EnvHelper()
        search_handler = Search.get_search_handler(env_helper)

        # then
        assert isinstance(search_handler, AzurePostgresHandler), \
            f"Expected AzurePostgresHandler but got {type(search_handler).__name__}"
        assert env_helper.DATABASE_TYPE == "PostgreSQL"
