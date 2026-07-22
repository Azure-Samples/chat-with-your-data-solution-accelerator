"""Tests for src/functions/add_url/blueprint.py.

Mirrors ``tests/functions/batch_start/test_blueprint.py`` for the
HTTP-trigger exception ladder + monkeypatch seam, and asserts the
add_url-specific parser-dispatch helper. ``_execute`` is the seam
so tests do not need a real credential, a real Search service, or
live HTTPS traffic.
"""

import json
import logging
from collections.abc import Awaitable, Callable, Sequence

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument, SearchResult
from functions.add_url import blueprint as bp_module
from functions.add_url.blueprint import _parser_key_for_url, add_url
from functions.add_url.handler import AddUrlRequest, AddUrlResponse
from functions.core import search_resolution
from functions.function_app import app

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
    assert AddUrlResponse.model_validate(payload).model_dump() == payload


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
    req = _make_req(json.dumps({"url": "https://example.invalid/", "evil": 1}).encode())
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


# ---------------------------------------------------------------------------
# _execute integration -- ensure_schema wiring
# ---------------------------------------------------------------------------
#
# Mirrors the batch_push blueprint coverage: the rest of this file
# monkeypatches `_execute` away; these two tests exercise the real
# body to prove `await search_provider.ensure_schema()` is wired
# before the handler and that `aclose` still runs when ensure_schema
# raises.


class _StubCredCM:
    """Async context manager whose body is a sentinel credential."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _StubCredProvider:
    def __init__(self, **_kwargs: object) -> None:
        pass

    async def get_credential(self) -> _StubCredCM:
        return _StubCredCM()


def _patch_execute_collaborators(
    monkeypatch: pytest.MonkeyPatch,
    search_stub: object,
    *,
    record: list[str],
) -> None:
    """Wire every registry + handler `_execute` reaches.

    `record` collects a call-order trail across `ensure_schema`,
    `add_url_handler`, and `aclose` so tests can assert the schema
    bootstrap runs **before** the handler and that `aclose` still
    runs when `ensure_schema` raises.
    """
    monkeypatch.setattr(
        bp_module.credentials_registry,
        "select_default",
        lambda _cid: "managed_identity",
    )
    monkeypatch.setattr(
        bp_module.credentials_registry.registry, "get", lambda _key: _StubCredProvider
    )
    parser = type("Parser", (), {"__init__": lambda self, **_kw: None})
    monkeypatch.setattr(
        bp_module.ingestion_parsers_registry.registry, "get", lambda _key: parser
    )

    class _Embedder:
        def __init__(self, **_kw: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        bp_module.embedders_registry.registry, "get", lambda _key: _Embedder
    )
    monkeypatch.setattr(
        search_resolution.search_registry.registry,
        "get",
        lambda _key: lambda **_kw: search_stub,
    )

    async def _stub_handler(*_a: object, **_kw: object) -> list[SearchDocument]:
        record.append("add_url_handler")
        return []

    monkeypatch.setattr(bp_module, "add_url_handler", _stub_handler)


@pytest.mark.asyncio
async def test_execute_calls_ensure_schema_before_handler_and_aclose_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []

    class _StubSearch(BaseSearch):
        def __init__(self, **_kw: object) -> None:
            pass

        async def search(self, query: str, **_kwargs: object) -> Sequence[SearchResult]:
            return []

        async def delete_by_source(self, source: str) -> int:
            return 0

        async def ensure_schema(self) -> None:
            record.append("ensure_schema")

        async def aclose(self) -> None:
            record.append("aclose")

    _patch_execute_collaborators(monkeypatch, _StubSearch(), record=record)
    settings = AppSettings()
    request = AddUrlRequest(
        url="https://example.invalid/file.txt",
        ingestion_job_id="00000000-0000-0000-0000-000000000099",
    )

    await bp_module._execute(request, settings)

    # The DDL bootstrap MUST land before the handler runs so the
    # first add_url request on a fresh pgvector deploy does not hit
    # `relation "documents" does not exist`. Cleanup still runs.
    assert record == ["ensure_schema", "add_url_handler", "aclose"]


@pytest.mark.asyncio
async def test_execute_propagates_ensure_schema_failure_and_still_closes_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []

    class _FailingSearch(BaseSearch):
        def __init__(self, **_kw: object) -> None:
            pass

        async def search(self, query: str, **_kwargs: object) -> Sequence[SearchResult]:
            return []

        async def delete_by_source(self, source: str) -> int:
            return 0

        async def ensure_schema(self) -> None:
            record.append("ensure_schema")
            raise AzureError("ddl rejected")

        async def aclose(self) -> None:
            record.append("aclose")

    _patch_execute_collaborators(monkeypatch, _FailingSearch(), record=record)
    settings = AppSettings()
    request = AddUrlRequest(
        url="https://example.invalid/file.txt",
        ingestion_job_id="00000000-0000-0000-0000-000000000099",
    )

    with pytest.raises(AzureError):
        await bp_module._execute(request, settings)

    # Handler never runs (schema bootstrap is its precondition); the
    # `finally: aclose` on the search provider must still fire so we
    # do not leak the asyncpg pool / HTTP client.
    assert record == ["ensure_schema", "aclose"]
    assert "add_url_handler" not in record
