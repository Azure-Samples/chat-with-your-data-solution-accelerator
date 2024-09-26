import hashlib
import json
from unittest.mock import ANY

from azure.functions import QueueMessage
import pytest
from pytest_httpserver import HTTPServer
from tests.functional.app_config import AppConfig
from tests.request_matching import RequestMatcher, verify_request_made
from tests.constants import (
    AZURE_STORAGE_CONFIG_FILE_NAME,
    AZURE_STORAGE_CONFIG_CONTAINER_NAME,
    COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
    COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
)
from backend.batch.batch_push_results import batch_push_results

pytestmark = pytest.mark.functional

FILE_NAME = "image.jpg"


@pytest.fixture
def message(app_config: AppConfig):
    return QueueMessage(
        body=json.dumps(
            {
                "topic": "topic",
                "subject": f"/blobServices/default/{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/documents/blobs/{FILE_NAME}",
                "eventType": "Microsoft.Storage.BlobCreated",
                "id": "id",
                "data": {
                    "api": "PutBlob",
                    "clientRequestId": "46093109-6e51-437f-aa0e-e6912a80a010",
                    "requestId": "5de84904-c01e-006b-47bb-a28f94000000",
                    "eTag": "0x8DC70D2C41ED398",
                    "contentType": "image/jpeg",
                    "contentLength": 115310,
                    "blobType": "BlockBlob",
                    "url": f"https://{app_config.get('AZURE_BLOB_ACCOUNT_NAME')}.blob.core.windows.net/documents/{FILE_NAME}",
                    "sequencer": "00000000000000000000000000005E450000000000001f49",
                    "storageDiagnostics": {
                        "batchId": "952bdc2e-6006-0000-00bb-a20860000000"
                    },
                },
                "dataVersion": "",
                "metadataVersion": "1",
                "eventTime": "2024-05-10T09:22:51.5565464Z",
            }
        )
    )


@pytest.fixture(autouse=True)
def setup_blob_metadata_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}",
        method="HEAD",
    ).respond_with_data()

    httpserver.expect_request(
        f"/{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}",
        method="PUT",
    ).respond_with_data()


@pytest.fixture(autouse=True)
def setup_caption_response(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_oneshot_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_VISION_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": app_config.get("AZURE_OPENAI_VISION_MODEL"),
            "usage": {
                "prompt_tokens": 58,
                "completion_tokens": 68,
                "total_tokens": 126,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "This is a caption for the image",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )


def test_config_file_is_retrieved_from_storage(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/{AZURE_STORAGE_CONFIG_CONTAINER_NAME}/{AZURE_STORAGE_CONFIG_FILE_NAME}",
            method="GET",
            headers={
                "Authorization": ANY,
            },
            times=1,
        ),
    )


def test_image_passed_to_computer_vision_to_generate_image_embeddings(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    request = verify_request_made(
        httpserver,
        RequestMatcher(
            path=COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
            method=COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
            json={
                "url": ANY,
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
    )[0]

    assert request.get_json()["url"].startswith(
        f"{app_config.get('AZURE_STORAGE_ACCOUNT_ENDPOINT')}{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}"
    )


def test_image_passed_to_llm_to_generate_caption(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    request = verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get('AZURE_OPENAI_VISION_MODEL')}/chat/completions",
            method="POST",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": """You are an assistant that generates rich descriptions of images.
You need to be accurate in the information you extract and detailed in the descriptons you generate.
Do not abbreviate anything and do not shorten sentances. Explain the image completely.
If you are provided with an image of a flow chart, describe the flow chart in detail.
If the image is mostly text, use OCR to extract the text as it is displayed in the image.""",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": "Describe this image in detail. Limit the response to 500 words.",
                                "type": "text",
                            },
                            {"image_url": {"url": ANY}, "type": "image_url"},
                        ],
                    },
                ],
                "model": app_config.get("AZURE_OPENAI_VISION_MODEL"),
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
    )[0]

    assert request.get_json()["messages"][1]["content"][1]["image_url"][
        "url"
    ].startswith(
        f"{app_config.get('AZURE_STORAGE_ACCOUNT_ENDPOINT')}{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}"
    )


def test_embeddings_generated_for_caption(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/openai/deployments/{app_config.get_from_json('AZURE_OPENAI_EMBEDDING_MODEL_INFO','model')}/embeddings",
            method="POST",
            json={
                "input": ["This is a caption for the image"],
                "model": app_config.get_from_json(
                    "AZURE_OPENAI_EMBEDDING_MODEL_INFO", "model"
                ),
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


def test_metadata_is_updated_after_processing(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}",
            method="PUT",
            headers={
                "Authorization": ANY,
                # Note: We cannot assert on this header, as the mock server
                # drops headers containing underscores, although Azure Storage
                # accepts it
                # "x-ms-meta-embeddings_added": "true"
            },
            query_string="comp=metadata",
            times=1,
        ),
    )


def test_makes_correct_call_to_list_search_indexes(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path="/indexes",
            method="GET",
            headers={
                "Accept": "application/json;odata.metadata=minimal",
                "Api-Key": app_config.get("AZURE_SEARCH_KEY"),
            },
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )


def test_makes_correct_call_to_create_documents_search_index(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path="/indexes",
            method="POST",
            headers={
                "Accept": "application/json;odata.metadata=minimal",
                "Api-Key": app_config.get("AZURE_SEARCH_KEY"),
            },
            query_string="api-version=2023-10-01-Preview",
            json={
                "name": app_config.get("AZURE_SEARCH_INDEX"),
                "fields": [
                    {
                        "name": app_config.get("AZURE_SEARCH_FIELDS_ID"),
                        "type": "Edm.String",
                        "key": True,
                        "retrievable": True,
                        "searchable": False,
                        "filterable": True,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_CONTENT_COLUMN"),
                        "type": "Edm.String",
                        "key": False,
                        "retrievable": True,
                        "searchable": True,
                        "filterable": False,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_CONTENT_VECTOR_COLUMN"),
                        "type": "Collection(Edm.Single)",
                        "searchable": True,
                        "dimensions": 2,
                        "vectorSearchProfile": "myHnswProfile",
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_FIELDS_METADATA"),
                        "type": "Edm.String",
                        "key": False,
                        "retrievable": True,
                        "searchable": True,
                        "filterable": False,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_TITLE_COLUMN"),
                        "type": "Edm.String",
                        "key": False,
                        "retrievable": True,
                        "searchable": True,
                        "filterable": True,
                        "sortable": False,
                        "facetable": True,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_SOURCE_COLUMN"),
                        "type": "Edm.String",
                        "key": False,
                        "retrievable": True,
                        "searchable": True,
                        "filterable": True,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_CHUNK_COLUMN"),
                        "type": "Edm.Int32",
                        "key": False,
                        "retrievable": True,
                        "searchable": False,
                        "filterable": True,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": app_config.get("AZURE_SEARCH_OFFSET_COLUMN"),
                        "type": "Edm.Int32",
                        "key": False,
                        "retrievable": True,
                        "searchable": False,
                        "filterable": True,
                        "sortable": False,
                        "facetable": False,
                    },
                    {
                        "name": "image_vector",
                        "type": "Collection(Edm.Single)",
                        "searchable": True,
                        "dimensions": 3,
                        "vectorSearchProfile": "myHnswProfile",
                    },
                ],
                "semantic": {
                    "configurations": [
                        {
                            "name": app_config.get(
                                "AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG"
                            ),
                            "prioritizedFields": {
                                "prioritizedContentFields": [
                                    {
                                        "fieldName": app_config.get(
                                            "AZURE_SEARCH_CONTENT_COLUMN"
                                        )
                                    }
                                ]
                            },
                        }
                    ]
                },
                "vectorSearch": {
                    "profiles": [
                        {"name": "myHnswProfile", "algorithm": "default"},
                        {
                            "name": "myExhaustiveKnnProfile",
                            "algorithm": "default_exhaustive_knn",
                        },
                    ],
                    "algorithms": [
                        {
                            "name": "default",
                            "kind": "hnsw",
                            "hnswParameters": {
                                "m": 4,
                                "efConstruction": 400,
                                "efSearch": 500,
                                "metric": "cosine",
                            },
                        },
                        {
                            "name": "default_exhaustive_knn",
                            "kind": "exhaustiveKnn",
                            "exhaustiveKnnParameters": {"metric": "cosine"},
                        },
                    ],
                },
            },
            times=1,
        ),
    )


def test_makes_correct_call_to_store_documents_in_search_index(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    expected_file_path = f"{app_config.get('AZURE_BLOB_CONTAINER_NAME')}/{FILE_NAME}"
    expected_source_url = (
        f"{app_config.get('AZURE_STORAGE_ACCOUNT_ENDPOINT')}{expected_file_path}"
    )
    hash_key = hashlib.sha1(f"{expected_source_url}_1".encode("utf-8")).hexdigest()
    expected_id = f"doc_{hash_key}"
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')/docs/search.index",
            method="POST",
            headers={
                "Accept": "application/json;odata.metadata=none",
                "Content-Type": "application/json",
                "Api-Key": app_config.get("AZURE_SEARCH_KEY"),
            },
            query_string="api-version=2023-10-01-Preview",
            json={
                "value": [
                    {
                        "id": expected_id,
                        "content": "This is a caption for the image",
                        "content_vector": [
                            0.018990106880664825,
                            -0.0073809814639389515,
                        ],
                        "image_vector": [1.0, 2.0, 3.0],
                        "metadata": json.dumps(
                            {
                                "id": expected_id,
                                "title": f"/{expected_file_path}",
                                "source": expected_source_url,
                            }
                        ),
                        "title": f"/{expected_file_path}",
                        "source": expected_source_url,
                        "@search.action": "upload",
                    }
                ]
            },
            times=1,
        ),
    )
