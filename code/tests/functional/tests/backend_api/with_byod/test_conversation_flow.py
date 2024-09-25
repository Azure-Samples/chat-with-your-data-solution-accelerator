import json
import pytest
from pytest_httpserver import HTTPServer
from unittest.mock import patch
import requests
from string import Template

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


@pytest.fixture(scope="function", autouse=True)
def setup_default_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_MODEL_INFO','model')}/chat/completions",
        method="POST",
    ).respond_with_data(
        Template(
            r"""data: {"id":"92f715be-cfc4-4ae6-80f8-c86b7955f6af","model":"$model","created":1712077271,"object":"extensions.chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","context":{"citations":[{"content":"document","title":"/documents/doc.pdf","url":{"id": "id", "source": "source", "title": "title", "chunk": 46, "chunk_id": null},"filepath":null,"chunk_id":"0"}],"intent":"[\"intent\"]"}},"end_turn":false,"finish_reason":null}]}

data: {"id":"92f715be-cfc4-4ae6-80f8-c86b7955f6af","model":"$model","created":1712077271,"object":"extensions.chat.completion.chunk","choices":[{"index":0,"delta":{"content":"42 is the meaning of life"},"end_turn":false,"finish_reason":null}],"system_fingerprint":"fp_68a7d165bf"}

data: {"id":"92f715be-cfc4-4ae6-80f8-c86b7955f6af","model":"$model","created":1712077271,"object":"extensio@ns.chat.completion.chunk","choices":[{"index":0,"delta":{},"end_turn":true,"finish_reason":"stop"}]}

data: [DONE]
"""
        ).substitute(model=app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"))
    )

    yield

    httpserver.check()


@patch(
    "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
)
def test_azure_byod_responds_successfully_when_streaming(
    get_active_config_or_default_mock,
    app_url: str,
    app_config: AppConfig,
):
    get_active_config_or_default_mock.return_value.prompts.conversational_flow = "byod"

    # when
    response = requests.post(f"{app_url}{path}", json=body)

    # then
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json-lines"

    response_lines = response.text.splitlines()
    assert len(response_lines) == 3

    final_response_json = json.loads(response_lines[-1])
    assert final_response_json == {
        "id": "92f715be-cfc4-4ae6-80f8-c86b7955f6af",
        "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
        "created": 1712077271,
        "object": "extensions.chat.completion.chunk",
        "choices": [
            {
                "messages": [
                    {
                        "content": '{"citations": [{"content": "[/documents/doc.pdf](source)\\n\\n\\ndocument", "id": "id", "chunk_id": 46, "title": "/documents/doc.pdf", "filepath": "doc.pdf", "url": "[/documents/doc.pdf](source)"}]}',
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
    }


@patch(
    "backend.batch.utilities.helpers.config.config_helper.ConfigHelper.get_active_config_or_default"
)
def test_post_makes_correct_call_to_azure_openai(
    get_active_config_or_default_mock,
    app_url: str,
    app_config: AppConfig,
    httpserver: HTTPServer,
):
    get_active_config_or_default_mock.return_value.prompts.conversational_flow = "byod"

    # when
    requests.post(f"{app_url}{path}", json=body)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_MODEL_INFO','model')}/chat/completions",
            method="POST",
            json={
                "messages": body["messages"],
                "model": app_config.get_from_json("AZURE_OPENAI_MODEL_INFO", "model"),
                "temperature": 0.0,
                "max_tokens": 1000,
                "top_p": 1.0,
                "stop": None,
                "stream": True,
                "data_sources": [
                    {
                        "type": "azure_search",
                        "parameters": {
                            "endpoint": app_config.get("AZURE_SEARCH_SERVICE"),
                            "index_name": app_config.get("AZURE_SEARCH_INDEX"),
                            "fields_mapping": {
                                "content_fields": ["content"],
                                "vector_fields": [
                                    app_config.get("AZURE_SEARCH_CONTENT_VECTOR_COLUMN")
                                ],
                                "title_field": "title",
                                "url_field": app_config.get(
                                    "AZURE_SEARCH_FIELDS_METADATA"
                                ),
                                "filepath_field": "filepath",
                            },
                            "filter": app_config.get("AZURE_SEARCH_FILTER"),
                            "in_scope": True,
                            "top_n_documents": 5,
                            "embedding_dependency": {
                                "type": "deployment_name",
                                "deployment_name": "some-embedding-model",
                            },
                            "query_type": "vector_simple_hybrid",
                            "semantic_configuration": "",
                            "role_information": "You are an AI assistant that helps people find information.",
                            "authentication": {
                                "type": "api_key",
                                "key": app_config.get("AZURE_SEARCH_KEY"),
                            },
                        },
                    }
                ],
            },
            headers={
                "api-key": app_config.get("AZURE_OPENAI_API_KEY"),
            },
            query_string="api-version=2024-02-01",
            times=1,
        ),
    )
