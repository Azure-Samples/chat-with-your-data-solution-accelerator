"""Pillar: Stable Core / Phase: 6 -- tests for v2/src/functions/batch_push/blueprint.py.

Mirrors the structure of ``tests/functions/batch_start/test_blueprint.py``:
the route body is exercised via the private ``_execute`` seam (which
tests monkeypatch) so we cover envelope parsing + decorator wiring
without spinning up Azurite, Foundry IQ, or a real Search service.

Decorator-internal branches (warning vs exception, log shape) are
covered exhaustively in ``tests/functions/core/test_exception_mapping.py``;
here we only assert the decorator IS wired around the queue trigger
function (one ``ValidationError`` + one ``AzureError`` + one generic
``Exception`` case prove the wrap).
"""

import json
import logging
from collections.abc import Awaitable, Callable, Sequence

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError
from pydantic import ValidationError

from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument, SearchResult
from functions.batch_push import blueprint as bp_module
from functions.batch_push.blueprint import _parser_key_for_filename, batch_push
from functions.core import search_resolution
from functions.core.contracts import BatchPushQueueMessage
from functions.function_app import app


# Minimal env that satisfies AppSettings + nested cross-field validators.
# Mirrors the cosmosdb fixture in tests/functions/batch_start/test_blueprint.py.
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
    execute: Callable[[BatchPushQueueMessage, AppSettings], Awaitable[list[SearchDocument]]],
    settings: AppSettings | None = None,
) -> None:
    resolved = settings or AppSettings()
    monkeypatch.setattr(bp_module, "get_settings", lambda: resolved)
    monkeypatch.setattr(bp_module, "_execute", execute)


def _make_msg(envelope: BatchPushQueueMessage | bytes) -> func.QueueMessage:
    body = envelope if isinstance(envelope, bytes) else envelope.model_dump_json().encode()
    return func.QueueMessage(body=body)


# ---------------------------------------------------------------------------
# _parser_key_for_filename helper
# ---------------------------------------------------------------------------


def test_parser_key_for_filename_strips_dot_and_lowercases() -> None:
    assert _parser_key_for_filename("report.PDF") == "pdf"
    assert _parser_key_for_filename("notes.txt") == "txt"
    assert _parser_key_for_filename("path/with/subdir/file.MD") == "md"


def test_parser_key_for_filename_returns_empty_for_no_extension() -> None:
    # Empty key intentionally bubbles into Registry.get -> KeyError ->
    # decorator's generic Exception branch -> runtime retry -> poison.
    assert _parser_key_for_filename("README") == ""


# ---------------------------------------------------------------------------
# Queue trigger happy path + envelope dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_parses_envelope_and_dispatches_to_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = BatchPushQueueMessage(
        container_name="documents", filename="a.txt", ingestion_job_id="job-1"
    )
    captured: dict[str, object] = {}

    async def fake_execute(
        message: BatchPushQueueMessage, settings: AppSettings
    ) -> list[SearchDocument]:
        captured["message"] = message
        captured["settings_type"] = type(settings).__name__
        return [
            SearchDocument(
                id="a.txt__0",
                content="x",
                title="a.txt",
                content_vector=[0.1],
            )
        ]

    _patch_route_deps(monkeypatch, fake_execute)

    # Queue trigger returns None per the wire contract; the documents
    # list is an internal _execute return value for downstream tests.
    result = await batch_push(_make_msg(envelope))

    assert result is None
    assert isinstance(captured["message"], BatchPushQueueMessage)
    parsed = captured["message"]
    assert isinstance(parsed, BatchPushQueueMessage)
    assert parsed.container_name == "documents"
    assert parsed.filename == "a.txt"
    assert parsed.ingestion_job_id == "job-1"
    assert captured["settings_type"] == "AppSettings"


# ---------------------------------------------------------------------------
# log_queue_errors decorator wiring -- one case per branch is enough
# (full ladder coverage lives in test_exception_mapping.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_envelope_raises_validation_error_and_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="functions.core.exception_mapping")

    # Missing required ``filename`` + ``container_name`` -> ValidationError
    # bubbles through parse_push_message; the decorator catches, logs
    # warning with structured extras, then re-raises so the runtime
    # engages retry -> poison.
    with pytest.raises(ValidationError):
        await batch_push(_make_msg(json.dumps({}).encode()))

    record = next(r for r in caplog.records if r.message == "batch_push queue message validation failed")
    assert record.levelno == logging.WARNING
    assert record.exc_info is None  # warning, not exception
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_azure_error_in_execute_reraises_and_logs_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        message: BatchPushQueueMessage, settings: AppSettings
    ) -> list[SearchDocument]:
        raise AzureError("upstream blob 503")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    envelope = BatchPushQueueMessage(
        container_name="documents", filename="b.txt", ingestion_job_id="job-2"
    )

    with pytest.raises(AzureError):
        await batch_push(_make_msg(envelope))

    record = next(
        r for r in caplog.records if r.message == "batch_push queue handler storage call failed"
    )
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None  # logger.exception attaches traceback
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_in_execute_reraises_safety_net(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        message: BatchPushQueueMessage, settings: AppSettings
    ) -> list[SearchDocument]:
        raise RuntimeError("totally unexpected")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    envelope = BatchPushQueueMessage(
        container_name="documents", filename="c.txt", ingestion_job_id="job-3"
    )

    with pytest.raises(RuntimeError):
        await batch_push(_make_msg(envelope))

    record = next(r for r in caplog.records if r.message == "batch_push queue handler failed")
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


def test_batch_push_route_registered_on_app() -> None:
    # Importing function_app must register the batch_push blueprint.
    function_names = {fb._function._name for fb in app._function_builders}  # type: ignore[attr-defined]
    assert "batch_push" in function_names
    # Regression: previously registered routes still present.
    assert "batch_start" in function_names
    assert "health" in function_names


# ---------------------------------------------------------------------------
# _execute integration -- ensure_schema wiring
# ---------------------------------------------------------------------------
#
# These tests exercise the real `_execute` (the rest of the file
# monkeypatches it away). They stub every collaborator the body
# touches so we never hit Azurite, Foundry IQ, a real Search service,
# or a real asyncpg pool. The point of these two tests is narrow:
# prove that `await search_provider.ensure_schema()` is wired into
# `_execute` and that ordering + cleanup semantics are correct.


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


class _StubContainerClient:
    """Async CM standing in for azure.storage.blob.aio.ContainerClient."""

    def __init__(self, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_StubContainerClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _patch_execute_collaborators(
    monkeypatch: pytest.MonkeyPatch,
    search_stub: object,
    *,
    record: list[str],
) -> None:
    """Wire every registry + transient `_execute` reaches.

    `record` collects a call-order trail across `ensure_schema`,
    `batch_push_handler`, and `aclose` so tests can assert the
    schema bootstrap runs **before** the handler and that `aclose`
    still runs when `ensure_schema` raises.
    """
    monkeypatch.setattr(bp_module.credentials_registry, "select_default", lambda _cid: "managed_identity")
    monkeypatch.setattr(
        bp_module.credentials_registry.registry, "get", lambda _key: _StubCredProvider
    )
    parser = type("Parser", (), {"__init__": lambda self, **_kw: None})
    monkeypatch.setattr(bp_module.ingestion_parsers_registry.registry, "get", lambda _key: parser)

    class _Embedder:
        def __init__(self, **_kw: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(bp_module.embedders_registry.registry, "get", lambda _key: _Embedder)
    monkeypatch.setattr(search_resolution.search_registry.registry, "get", lambda _key: lambda **_kw: search_stub)
    monkeypatch.setattr(bp_module, "ContainerClient", _StubContainerClient)
    monkeypatch.setattr(
        bp_module,
        "resolve_storage_endpoints",
        lambda _s: ("https://stcwyd001.blob.core.windows.net", ""),
    )

    async def _stub_handler(**_kw: object) -> list[SearchDocument]:
        record.append("batch_push_handler")
        return []

    monkeypatch.setattr(bp_module, "batch_push_handler", _stub_handler)


@pytest.mark.asyncio
async def test_execute_calls_ensure_schema_before_handler_and_aclose_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []

    class _StubSearch(BaseSearch):
        def __init__(self, **_kw: object) -> None:
            pass

        async def search(
            self, query: str, **_kwargs: object
        ) -> Sequence[SearchResult]:
            return []

        async def delete_by_source(self, source: str) -> int:
            return 0

        async def ensure_schema(self) -> None:
            record.append("ensure_schema")

        async def aclose(self) -> None:
            record.append("aclose")

    _patch_execute_collaborators(monkeypatch, _StubSearch(), record=record)
    settings = AppSettings()
    envelope = BatchPushQueueMessage(
        container_name="documents", filename="a.txt", ingestion_job_id="job-x"
    )

    await bp_module._execute(envelope, settings)

    # The DDL bootstrap MUST land before the handler runs (otherwise
    # the first ingestion message on a fresh pgvector deploy hits
    # `relation "documents" does not exist`). Cleanup must still run.
    assert record == ["ensure_schema", "batch_push_handler", "aclose"]


@pytest.mark.asyncio
async def test_execute_propagates_ensure_schema_failure_and_still_closes_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[str] = []

    class _FailingSearch(BaseSearch):
        def __init__(self, **_kw: object) -> None:
            pass

        async def search(
            self, query: str, **_kwargs: object
        ) -> Sequence[SearchResult]:
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
    envelope = BatchPushQueueMessage(
        container_name="documents", filename="a.txt", ingestion_job_id="job-x"
    )

    with pytest.raises(AzureError):
        await bp_module._execute(envelope, settings)

    # Handler never runs (schema bootstrap is its precondition); the
    # `finally: aclose` on the search provider must still fire so we
    # do not leak the asyncpg pool / HTTP client.
    assert record == ["ensure_schema", "aclose"]
    assert "batch_push_handler" not in record
