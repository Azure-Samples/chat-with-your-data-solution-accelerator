import json
import os
import sys
from unittest.mock import ANY

from azure.functions import QueueMessage
import pytest
from pytest_httpserver import HTTPServer
from tests.functional.app_config import AppConfig
from tests.request_matching import RequestMatcher, verify_request_made
from tests.constants import (
    AZURE_STORAGE_CONFIG_FILE_NAME,
    AZURE_STORAGE_CONFIG_CONTAINER_NAME,
)

sys.path.append(
    os.path.join(os.path.dirname(sys.path[0]), "..", "..", "backend", "batch")
)

from backend.batch.batch_push_results import batch_push_results  # noqa: E402

pytestmark = pytest.mark.functional

FILE_NAME = "test.pdf"


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
                    "clientRequestId": "73a48942-0eae-11ef-9576-0242ac110002",
                    "requestId": "9cc44179-401e-005a-4fbb-a2e687000000",
                    "eTag": "0x8DC70D257E6452E",
                    "contentType": "application/pdf",
                    "contentLength": 544811,
                    "blobType": "BlockBlob",
                    "url": f"https://{app_config.get('AZURE_BLOB_ACCOUNT_NAME')}.blob.core.windows.net/documents/{FILE_NAME}",
                    "sequencer": "00000000000000000000000000036029000000000017251c",
                    "storageDiagnostics": {
                        "batchId": "c98008b9-e006-007c-00bb-a2ae9f000000"
                    },
                },
                "dataVersion": "",
                "metadataVersion": "1",
                "eventTime": "2024-05-10T09:22:51.5565464Z",
            }
        )
    )


@pytest.fixture(autouse=True)
def completions_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/datasources('{app_config.get('AZURE_SEARCH_DATASOURCE_NAME')}')",  # ?api-version=2023-10-01-Preview",
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


def test_integrated_vectorization_datasouce_created(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/datasources('{app_config.get('AZURE_SEARCH_DATASOURCE_NAME')}')",
            method="PUT",
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )


def test_integrated_vectorization_index_created(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')",
            method="PUT",
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )


def test_integrated_vectorization_skillset_created(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/skillsets('{app_config.get('AZURE_SEARCH_INDEX')}-skillset')",
            method="PUT",
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )


def test_integrated_vectorization_indexer_created(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexers('{app_config.get('AZURE_SEARCH_INDEXER_NAME')}')",
            method="PUT",
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )


def test_integrated_vectorization_indexer_run(
    message: QueueMessage, httpserver: HTTPServer, app_config: AppConfig
):
    # when
    batch_push_results.build().get_user_function()(message)

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path=f"/indexers('{app_config.get('AZURE_SEARCH_INDEXER_NAME')}')/search.run",
            method="POST",
            query_string="api-version=2023-10-01-Preview",
            times=1,
        ),
    )
