import re
import pytest
from pytest_httpserver import HTTPServer
from tests.functional.app_config import AppConfig
from tests.constants import (
    AZURE_STORAGE_CONFIG_CONTAINER_NAME,
    AZURE_STORAGE_CONFIG_FILE_NAME,
    COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
    COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    COMPUTER_VISION_VECTORIZE_TEXT_PATH,
    COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
)


@pytest.fixture(scope="function", autouse=True)
def setup_default_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/{AZURE_STORAGE_CONFIG_CONTAINER_NAME}/{AZURE_STORAGE_CONFIG_FILE_NAME}",
        method="HEAD",
    ).respond_with_data()

    httpserver.expect_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_EMBEDDING_MODEL')}/embeddings",
        method="POST",
    ).respond_with_json(
        {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": [0.018990106880664825, -0.0073809814639389515],
                    "index": 0,
                }
            ],
            "model": "text-embedding-ada-002",
        }
    )

    httpserver.expect_request(
        "/indexes",
        method="POST",
    ).respond_with_json({}, status=201)

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')",
        method="GET",
    ).respond_with_json({})

    httpserver.expect_request(
        "/contentsafety/text:analyze",
        method="POST",
    ).respond_with_json(
        {
            "blocklistsMatch": [],
            "categoriesAnalysis": [],
        }
    )

    httpserver.expect_request(
        re.compile(
            f"/openai/deployments/({app_config.get('AZURE_OPENAI_MODEL')}|{app_config.get('AZURE_OPENAI_VISION_MODEL')})/chat/completions"
        ),
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
                        "content": "42 is the meaning of life",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')/docs/search.index",
        method="POST",
    ).respond_with_json(
        {
            "value": [
                {"key": "1", "status": True, "errorMessage": None, "statusCode": 201}
            ]
        }
    )

    httpserver.expect_request(
        "/sts/v1.0/issueToken",
        method="POST",
    ).respond_with_data("speech-token")

    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]})

    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_TEXT_PATH,
        COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]})

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')/docs/search.index",
        method="POST",
    ).respond_with_json(
        {
            "value": [
                {
                    "key": "some-key",
                    "status": True,
                    "errorMessage": None,
                    "statusCode": 201,
                }
            ]
        }
    )

    httpserver.expect_request(
        f"/datasources('{app_config.get('AZURE_SEARCH_DATASOURCE_NAME')}')",
        method="PUT",
    ).respond_with_json({}, status=201)

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')",
        method="PUT",
    ).respond_with_json({}, status=201)

    httpserver.expect_request(
        f"/skillsets('{app_config.get('AZURE_SEARCH_INDEX')}-skillset')",
        method="PUT",
    ).respond_with_json(
        {
            "name": f"{app_config.get('AZURE_SEARCH_INDEX')}-skillset",
            "description": "Extract entities, detect language and extract key-phrases",
            "skills": [
                {
                    "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
                    "name": "#3",
                    "description": None,
                    "context": None,
                    "inputs": [
                        {"name": "text", "source": "/document/content"},
                        {"name": "languageCode", "source": "/document/languageCode"},
                    ],
                    "outputs": [{"name": "textItems", "targetName": "pages"}],
                    "defaultLanguageCode": None,
                    "textSplitMode": "pages",
                    "maximumPageLength": 4000,
                },
            ],
        },
        status=201,
    )

    httpserver.expect_request(
        f"/indexers('{app_config.get('AZURE_SEARCH_INDEXER_NAME')}')",
        method="PUT",
    ).respond_with_json({}, status=201)

    httpserver.expect_request(
        f"/indexers('{app_config.get('AZURE_SEARCH_INDEXER_NAME')}')/search.run",
        method="POST",
    ).respond_with_json({}, status=202)

    yield

    httpserver.check()


@pytest.fixture(scope="function", autouse=True)
def prime_search_to_trigger_creation_of_index(
    httpserver: HTTPServer, app_config: AppConfig
):
    # first request should return no indexes
    httpserver.expect_oneshot_request(
        "/indexes",
        method="GET",
    ).respond_with_json({"value": []})

    # second request should return the index as it will have been "created"
    httpserver.expect_request(
        "/indexes",
        method="GET",
    ).respond_with_json({"value": [{"name": app_config.get("AZURE_SEARCH_INDEX")}]})

    httpserver.expect_request(
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
                    "metadata": '{"id": "doc_1", "source": "https://source", "title": "/documents/doc.pdf", "chunk": 95, "offset": 202738, "page_number": null}',
                    "title": "/documents/doc.pdf",
                    "source": "https://source",
                    "chunk": 95,
                    "offset": 202738,
                }
            ]
        }
    )


# This fixture can be overriden
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
                "enable_post_answering_prompt": False,
                "enable_content_safety": True,
            },
            "messages": {"post_answering_filter": "post answering filter"},
            "example": {
                "documents": '{"retrieved_documents":[{"[doc1]":{"content":"content"}}]}',
                "user_question": "user question",
                "answer": "answer",
            },
            "document_processors": [
                {
                    "document_type": "pdf",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "layout"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "txt",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "web"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "url",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "web"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "md",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "web"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "html",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "web"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "docx",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "docx"},
                    "use_advanced_image_processing": False,
                },
                {
                    "document_type": "jpg",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "layout"},
                    "use_advanced_image_processing": True,
                },
                {
                    "document_type": "png",
                    "chunking": {"strategy": "layout", "size": 500, "overlap": 100},
                    "loading": {"strategy": "layout"},
                    "use_advanced_image_processing": False,
                },
            ],
            "logging": {"log_user_interactions": True, "log_tokens": True},
            "orchestrator": {"strategy": "openai_function"},
            "integrated_vectorization_config": None,
        },
        headers={
            "Content-Type": "application/json",
            "Content-Range": "bytes 0-12882/12883",
        },
    )
