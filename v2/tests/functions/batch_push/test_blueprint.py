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
from collections.abc import Awaitable, Callable

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings, get_settings
from functions.batch_push import blueprint as bp_module
from functions.batch_push.blueprint import _parser_key_for_filename, batch_push
from functions.core.contracts import BatchPushQueueMessage


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
    execute: Callable[[BatchPushQueueMessage, AppSettings], Awaitable[list[dict[str, object]]]],
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
    ) -> list[dict[str, object]]:
        captured["message"] = message
        captured["settings_type"] = type(settings).__name__
        return [{"id": "a.txt__0", "content": "x", "title": "a.txt", "content_vector": [0.1]}]

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

    from pydantic import ValidationError

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
    ) -> list[dict[str, object]]:
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
    ) -> list[dict[str, object]]:
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
