"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/add_url/blueprint.py.

Mirrors ``tests/functions/batch_start/test_blueprint.py`` for the
HTTP-trigger exception ladder + monkeypatch seam, and asserts the
add_url-specific parser-dispatch helper. ``_execute`` is the seam
so tests do not need a real credential, a real Search service, or
live HTTPS traffic.
"""

import json
import logging
from collections.abc import Awaitable, Callable

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument
from functions.add_url import blueprint as bp_module
from functions.add_url.blueprint import _parser_key_for_url, add_url
from functions.add_url.handler import AddUrlRequest


# Minimal env that satisfies AppSettings + nested cross-field validators.
# Mirrors the fixture in tests/functions/batch_start/test_blueprint.py.
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
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-4.1",
    "AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini",
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
    execute: Callable[[AddUrlRequest, AppSettings], Awaitable[list[SearchDocument]]],
    settings: AppSettings | None = None,
) -> None:
    resolved = settings or AppSettings()
    monkeypatch.setattr(bp_module, "get_settings", lambda: resolved)
    monkeypatch.setattr(bp_module, "_execute", execute)


def _make_req(body: bytes) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/add_url",
        body=body,
        headers={"content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_happy_path_returns_200_with_ingestion_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_docs = [
        SearchDocument(
            id="https://example.invalid/page__0",
            content="hello",
            title="https://example.invalid/page",
            content_vector=[0.1, 0.2],
        ),
        SearchDocument(
            id="https://example.invalid/page__1",
            content="world",
            title="https://example.invalid/page",
            content_vector=[0.3, 0.4],
        ),
    ]

    async def fake_execute(
        request: AddUrlRequest, settings: AppSettings
    ) -> list[SearchDocument]:
        assert request.url == "https://example.invalid/page"
        assert request.ingestion_job_id == "job-1"
        return expected_docs

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(
        json.dumps(
            {"url": "https://example.invalid/page", "ingestion_job_id": "job-1"}
        ).encode()
    )

    resp = await add_url(req)

    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    payload = json.loads(resp.get_body())
    assert payload == {
        "ingestion_job_id": "job-1",
        "url": "https://example.invalid/page",
        "document_count": 2,
    }


@pytest.mark.asyncio
async def test_zero_documents_returns_200_with_zero_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute(
        request: AddUrlRequest, settings: AppSettings
    ) -> list[SearchDocument]:
        return []

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(
        json.dumps(
            {"url": "https://example.invalid/empty", "ingestion_job_id": "job-empty"}
        ).encode()
    )

    resp = await add_url(req)

    assert resp.status_code == 200
    payload = json.loads(resp.get_body())
    assert payload == {
        "ingestion_job_id": "job-empty",
        "url": "https://example.invalid/empty",
        "document_count": 0,
    }


@pytest.mark.asyncio
async def test_empty_body_returns_422_validation_error() -> None:
    req = _make_req(b"")
    resp = await add_url(req)
    assert resp.status_code == 422
    payload = json.loads(resp.get_body())
    assert payload["error"] == "validation_error"
    assert isinstance(payload["details"], list) and payload["details"]


@pytest.mark.asyncio
async def test_malformed_json_returns_422() -> None:
    req = _make_req(b"{ not json")
    resp = await add_url(req)
    assert resp.status_code == 422
    assert json.loads(resp.get_body())["error"] == "validation_error"


@pytest.mark.asyncio
async def test_missing_url_field_returns_422() -> None:
    req = _make_req(json.dumps({}).encode())
    resp = await add_url(req)
    assert resp.status_code == 422
    payload = json.loads(resp.get_body())
    assert payload["error"] == "validation_error"


@pytest.mark.asyncio
async def test_extra_field_returns_422_due_to_extra_forbid() -> None:
    req = _make_req(
        json.dumps({"url": "https://example.invalid/", "evil": 1}).encode()
    )
    resp = await add_url(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_azure_error_returns_502_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: AddUrlRequest, settings: AppSettings
    ) -> list[SearchDocument]:
        raise AzureError("upstream search boom")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(json.dumps({"url": "https://example.invalid/p"}).encode())

    resp = await add_url(req)

    assert resp.status_code == 502
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}
    record = next(
        r for r in caplog.records if r.message == "add_url storage call failed"
    )
    assert record.operation == "add_url"  # type: ignore[attr-defined]
    assert record.trigger == "http"  # type: ignore[attr-defined]
    assert record.status_code == 502  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_returns_500_safety_net(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: AddUrlRequest, settings: AppSettings
    ) -> list[SearchDocument]:
        raise RuntimeError("totally unexpected")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(json.dumps({"url": "https://example.invalid/p"}).encode())

    resp = await add_url(req)

    assert resp.status_code == 500
    assert json.loads(resp.get_body()) == {"error": "internal_server_error"}
    record = next(r for r in caplog.records if r.message == "add_url handler failed")
    assert record.status_code == 500  # type: ignore[attr-defined]


def test_add_url_route_registered_on_app() -> None:
    # Importing function_app must register the blueprint route.
    from functions.function_app import app

    function_names = {fb._function._name for fb in app._function_builders}  # type: ignore[attr-defined]
    assert "add_url" in function_names
    # Regression: batch_start, batch_push, and health still registered.
    assert "batch_start" in function_names
    assert "batch_push" in function_names
    assert "health" in function_names


# ---------------------------------------------------------------------------
# parser-dispatch helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected_key"),
    [
        ("https://example.invalid/file.pdf", "pdf"),
        ("https://example.invalid/file.txt", "txt"),
        ("https://example.invalid/Notes.MD", "md"),
        # Query strings + fragments are ignored.
        ("https://example.invalid/file.pdf?q=1#frag", "pdf"),
        # No extension on the URL path -> default to "txt".
        ("https://example.invalid/article", "txt"),
        ("https://example.invalid/", "txt"),
        # Multi-segment paths.
        ("https://example.invalid/a/b/c/document.docx", "docx"),
    ],
)
def test_parser_key_for_url(url: str, expected_key: str) -> None:
    assert _parser_key_for_url(url) == expected_key
