"""Tests for src/functions/batch_start/blueprint.py.

The blueprint composes ``functions/core/`` helpers (resolve
endpoints, storage_clients ctx manager, json_response, the
``map_function_exceptions`` decorator). Exception ladder logging
originates from the decorator's logger
``functions.core.exception_mapping``; ``_resolve_endpoints`` /
``_json_response`` do not live here (covered by
tests/functions/core/test_storage_endpoints.py and
tests/functions/core/test_http.py respectively).
"""

import json
import logging
from collections.abc import Awaitable, Callable

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings, get_settings
from functions.batch_start import blueprint as bp_module
from functions.batch_start.blueprint import batch_start
from functions.batch_start.models import BatchStartRequest, BatchStartResponse
from functions.core.contracts import BatchPushQueueMessage
from functions.function_app import app

# Minimal env that satisfies AppSettings + nested cross-field validators.
# Mirrors the cosmosdb fixture in tests/backend/core/test_settings.py.
_BASE_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_AI_SERVICE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_UAMI_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
    "AZURE_UAMI_PRINCIPAL_ID": "00000000-0000-0000-0000-000000000003",
    "AZURE_UAMI_RESOURCE_ID": "/subscriptions/x/resourceGroups/y/providers/.../id-cwyd001",
    "AZURE_AI_SERVICES_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/api/projects/proj",
    "AZURE_AI_AGENT_API_VERSION": "2025-05-01",
    "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_COSMOS_ACCOUNT_NAME": "cosmos-cwyd001",
    "AZURE_AI_SEARCH_ENDPOINT": "https://srch-cwyd001.search.windows.net",
    "AZURE_AI_SEARCH_NAME": "srch-cwyd001",
    "AZURE_STORAGE_ACCOUNT_NAME": "stcwyd001",
    "AZURE_STORAGE_BLOB_ENDPOINT": "",
    "AZURE_DOCUMENTS_CONTAINER": "documents",
    "AZURE_DOC_PROCESSING_QUEUE": "doc-processing",
    "AZURE_BACKEND_URL": "https://ca-back-cwyd001.example.azurecontainerapps.io",
    "AZURE_FRONTEND_URL": "https://app-front-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_URL": "https://func-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_NAME": "func-cwyd001",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _BASE_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _patch_route_deps(
    monkeypatch: pytest.MonkeyPatch,
    execute: Callable[
        [BatchStartRequest, AppSettings], Awaitable[list[BatchPushQueueMessage]]
    ],
    settings: AppSettings | None = None,
) -> None:
    resolved = settings or AppSettings()
    monkeypatch.setattr(bp_module, "get_settings", lambda: resolved)
    monkeypatch.setattr(bp_module, "_execute", execute)


def _make_req(body: bytes) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/batch_start",
        body=body,
        headers={"content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_happy_path_returns_200_with_ingestion_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued = [
        BatchPushQueueMessage(
            container_name="documents", filename="a.pdf", ingestion_job_id="job-1"
        ),
        BatchPushQueueMessage(
            container_name="documents", filename="b.pdf", ingestion_job_id="job-1"
        ),
    ]

    async def fake_execute(
        request: BatchStartRequest, settings: AppSettings
    ) -> list[BatchPushQueueMessage]:
        assert request.container_name == "documents"
        return enqueued

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(json.dumps({"container_name": "documents"}).encode())

    resp = await batch_start(req)

    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    payload = json.loads(resp.get_body())
    assert payload == {
        "ingestion_job_id": "job-1",
        "enqueued_count": 2,
        "filenames": ["a.pdf", "b.pdf"],
    }
    assert BatchStartResponse.model_validate(payload).model_dump() == payload


@pytest.mark.asyncio
async def test_empty_blob_listing_returns_200_with_null_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(
        request: BatchStartRequest, settings: AppSettings
    ) -> list[BatchPushQueueMessage]:
        return []

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(json.dumps({"container_name": "documents"}).encode())

    resp = await batch_start(req)

    assert resp.status_code == 200
    payload = json.loads(resp.get_body())
    assert payload == {"ingestion_job_id": None, "enqueued_count": 0, "filenames": []}


@pytest.mark.asyncio
async def test_empty_body_returns_422_validation_error() -> None:
    req = _make_req(b"")
    resp = await batch_start(req)
    assert resp.status_code == 422
    payload = json.loads(resp.get_body())
    assert payload["error"] == "validation_error"
    assert isinstance(payload["details"], list) and payload["details"]


@pytest.mark.asyncio
async def test_malformed_json_returns_422() -> None:
    req = _make_req(b"{ not json")
    resp = await batch_start(req)
    assert resp.status_code == 422
    assert json.loads(resp.get_body())["error"] == "validation_error"


@pytest.mark.asyncio
async def test_extra_field_returns_422_due_to_extra_forbid() -> None:
    req = _make_req(json.dumps({"container_name": "docs", "evil": 1}).encode())
    resp = await batch_start(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_azure_error_returns_502_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: BatchStartRequest, settings: AppSettings
    ) -> list[BatchPushQueueMessage]:
        raise AzureError("upstream boom")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(json.dumps({"container_name": "documents"}).encode())

    resp = await batch_start(req)

    assert resp.status_code == 502
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}
    record = next(
        r for r in caplog.records if r.message == "batch_start storage call failed"
    )
    assert record.operation == "batch_start"  # type: ignore[attr-defined]
    assert record.trigger == "http"  # type: ignore[attr-defined]
    assert record.status_code == 502  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_returns_500_safety_net(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: BatchStartRequest, settings: AppSettings
    ) -> list[BatchPushQueueMessage]:
        raise RuntimeError("totally unexpected")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(json.dumps({"container_name": "documents"}).encode())

    resp = await batch_start(req)

    assert resp.status_code == 500
    assert json.loads(resp.get_body()) == {"error": "internal_server_error"}
    record = next(
        r for r in caplog.records if r.message == "batch_start handler failed"
    )
    assert record.status_code == 500  # type: ignore[attr-defined]


def test_batch_start_route_registered_on_app() -> None:
    # Importing function_app must register the blueprint route.
    function_names = {fb._function._name for fb in app._function_builders}  # type: ignore[attr-defined]
    assert "batch_start" in function_names
    assert "health" in function_names  # regression: existing route still present
