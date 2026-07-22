"""Tests for src/functions/blob_event/blueprint.py.

Mirrors ``tests/functions/batch_push/test_blueprint.py``: the trigger
body is exercised via the private ``_execute`` seam (which tests
monkeypatch) so we cover dispatch + decorator wiring without opening a
real credential or Storage Queue. Decorator-internal branches are
covered exhaustively in ``tests/functions/core/test_exception_mapping.py``;
here we only assert the decorator IS wired around the queue trigger
function, plus a focused ``_execute`` translate-and-enqueue test.
"""

import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Self, cast

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchResult
from functions.blob_event import blueprint as bp_module
from functions.blob_event.blueprint import blob_event
from functions.blob_event.event_parser import BlobEventType
from functions.blob_event.handler import BlobEventOutcome
from functions.core import search_resolution
from functions.core.contracts import BatchPushQueueMessage
from functions.function_app import app

_DOCUMENTS_SUBJECT = (
    "/blobServices/default/containers/documents/blobs/Benefit_Options.pdf"
)


# Minimal env that satisfies AppSettings + nested cross-field validators.
# Mirrors the fixture in tests/functions/batch_push/test_blueprint.py.
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


def _event_body(
    subject: str, event_type: str = "Microsoft.Storage.BlobCreated"
) -> bytes:
    """Raw Event Grid blob event JSON, as delivered to the queue."""
    return json.dumps(
        {
            "topic": "/subscriptions/x/resourceGroups/y/providers/Microsoft.Storage/storageAccounts/stcwyd001",
            "subject": subject,
            "eventType": event_type,
            "id": "evt-1",
            "data": {
                "api": "PutBlob",
                "url": f"https://stcwyd001.blob.core.windows.net{subject}",
            },
            "dataVersion": "1",
        }
    ).encode("utf-8")


class _FakeQueueMessage:
    """Minimal stand-in for ``azure.functions.QueueMessage``.

    Only ``get_body()`` is read by the blueprint body.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    def get_body(self) -> bytes:
        return self._body


def _make_msg(
    subject: str, event_type: str = "Microsoft.Storage.BlobCreated"
) -> func.QueueMessage:
    return cast(func.QueueMessage, _FakeQueueMessage(_event_body(subject, event_type)))


def _patch_route_deps(
    monkeypatch: pytest.MonkeyPatch,
    execute: Callable[
        [func.QueueMessage, AppSettings], Awaitable[BlobEventOutcome | None]
    ],
    settings: AppSettings | None = None,
) -> None:
    resolved = settings or AppSettings()
    monkeypatch.setattr(bp_module, "get_settings", lambda: resolved)
    monkeypatch.setattr(bp_module, "_execute", execute)


@pytest.mark.asyncio
async def test_happy_path_dispatches_message_to_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_execute(
        msg: func.QueueMessage, settings: AppSettings
    ) -> BlobEventOutcome | None:
        captured["body"] = msg.get_body()
        captured["settings_type"] = type(settings).__name__
        return BlobEventOutcome(event_type=BlobEventType.CREATED, filename="a.pdf")

    _patch_route_deps(monkeypatch, fake_execute)

    # Queue trigger returns None per the wire contract; the envelope is an
    # internal _execute return value used by downstream assertions.
    result = await blob_event(_make_msg(_DOCUMENTS_SUBJECT))

    assert result is None
    assert captured["body"] == _event_body(_DOCUMENTS_SUBJECT)
    assert captured["settings_type"] == "AppSettings"


@pytest.mark.asyncio
async def test_azure_error_in_execute_reraises_and_logs_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        msg: func.QueueMessage, settings: AppSettings
    ) -> BlobEventOutcome | None:
        raise AzureError("queue 503")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")

    with pytest.raises(AzureError):
        await blob_event(_make_msg(_DOCUMENTS_SUBJECT))

    record = next(
        r
        for r in caplog.records
        if r.message == "blob_event queue handler storage call failed"
    )
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None  # logger.exception attaches traceback
    assert record.operation == "blob_event"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_in_execute_reraises_safety_net(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        msg: func.QueueMessage, settings: AppSettings
    ) -> BlobEventOutcome | None:
        raise RuntimeError("totally unexpected")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")

    with pytest.raises(RuntimeError):
        await blob_event(_make_msg(_DOCUMENTS_SUBJECT))

    record = next(
        r for r in caplog.records if r.message == "blob_event queue handler failed"
    )
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.operation == "blob_event"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_execute_skips_malformed_message_without_opening_clients() -> None:
    # A non-event body yields no subject, so _execute returns None before
    # any credential / queue client is opened (no monkeypatching needed).
    bad = cast(func.QueueMessage, _FakeQueueMessage(b"not-an-event"))
    result = await bp_module._execute(bad, AppSettings())
    assert result is None


@pytest.mark.asyncio
async def test_execute_enqueues_translated_envelope_to_doc_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []

    class _StubCredCM:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    class _StubCredProvider:
        def __init__(self, **_kw: object) -> None:
            pass

        async def get_credential(self) -> _StubCredCM:
            return _StubCredCM()

    class _StubQueueClient:
        queue_name = "doc-processing"

        def __init__(self, **_kw: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_exc: object) -> None:
            return None

        async def send_message(self, content: str) -> None:
            sent.append(content)

    monkeypatch.setattr(
        bp_module.credentials_registry,
        "select_default",
        lambda _cid: "managed_identity",
    )
    monkeypatch.setattr(
        bp_module.credentials_registry.registry, "get", lambda _key: _StubCredProvider
    )
    monkeypatch.setattr(bp_module, "QueueClient", _StubQueueClient)
    monkeypatch.setattr(
        bp_module,
        "resolve_storage_endpoints",
        lambda _s: (
            "https://stcwyd001.blob.core.windows.net",
            "https://stcwyd001.queue.core.windows.net",
        ),
    )

    result = await bp_module._execute(_make_msg(_DOCUMENTS_SUBJECT), AppSettings())

    assert result is not None
    assert result.event_type is BlobEventType.CREATED
    assert result.enqueued is not None
    assert result.enqueued.container_name == "documents"
    assert result.enqueued.filename == "Benefit_Options.pdf"
    # Exactly one CWYD envelope enqueued onto doc-processing; round-trips.
    assert len(sent) == 1
    assert BatchPushQueueMessage.model_validate_json(sent[0]) == result.enqueued


@pytest.mark.asyncio
async def test_execute_deindexes_on_blob_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A BlobDeleted event resolves the search provider and de-indexes the
    # blob's chunks; the doc-processing queue client is never opened. The
    # base env selects AzureSearch, so the pgvector pool branch is skipped.
    deleted_sources: list[str] = []

    class _StubCredCM:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    class _StubCredProvider:
        def __init__(self, **_kw: object) -> None:
            pass

        async def get_credential(self) -> _StubCredCM:
            return _StubCredCM()

    class _StubSearch(BaseSearch):
        def __init__(self, **_kw: object) -> None:
            pass

        async def search(self, query: str, **_kwargs: object) -> Sequence[SearchResult]:
            return []

        async def ensure_schema(self) -> None:
            return None

        async def delete_by_source(self, source: str) -> int:
            deleted_sources.append(source)
            return 5

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        bp_module.credentials_registry,
        "select_default",
        lambda _cid: "managed_identity",
    )
    monkeypatch.setattr(
        bp_module.credentials_registry.registry, "get", lambda _key: _StubCredProvider
    )
    monkeypatch.setattr(
        search_resolution.search_registry.registry, "get", lambda _key: _StubSearch
    )

    result = await bp_module._execute(
        _make_msg(_DOCUMENTS_SUBJECT, "Microsoft.Storage.BlobDeleted"), AppSettings()
    )

    assert result is not None
    assert result.event_type is BlobEventType.DELETED
    assert result.enqueued is None
    assert result.deleted_count == 5
    # de-index is keyed on the blob path (the indexed source).
    assert deleted_sources == ["Benefit_Options.pdf"]


def test_blob_event_route_registered_on_app() -> None:
    # Importing function_app must register the blob_event blueprint.
    function_names = {fb._function._name for fb in app._function_builders}  # type: ignore[attr-defined]
    assert "blob_event" in function_names
    # Regression: previously registered routes still present.
    assert "batch_push" in function_names
    assert "batch_start" in function_names
