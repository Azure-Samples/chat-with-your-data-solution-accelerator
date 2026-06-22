"""Tests for ``backend.services.ingestion``.

Pillar: Stable Core
Phase: 7 (Testing + Documentation -- admin-side ingestion helpers)
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace as NS
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from azure.core.exceptions import AzureError

import backend.services.ingestion as ingestion_module
from backend.core.settings import IngestionTrigger
from backend.models.admin import IngestUrlRequest, UploadResponse
from backend.services.ingestion import (
    MAX_UPLOAD_SIZE_BYTES,
    UploadRejected,
    _blob_name_for_url,
    ingest_url,
    reprocess_all,
    upload_document,
    validate_upload,
)
from functions.batch_start.models import BatchStartRequest
from functions.core.contracts import BatchPushQueueMessage


# ---------------------------------------------------------------------------
# _blob_name_for_url -- deterministic, flat, parseable blob filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        # Registered parser extensions are preserved.
        ("https://example.com/docs/report.pdf", "example.com_docs_report.pdf"),
        ("https://example.com/notes.DOCX", "example.com_notes.docx"),
        ("https://example.com/raw.txt", "example.com_raw.txt"),
        ("https://example.com/data.json", "example.com_data.json"),
        ("https://example.com/file.md?ref=x#top", "example.com_file.md"),
        # Ext-less / unknown URLs are web pages -> stored as .html so the
        # HtmlParser extracts clean text downstream.
        ("https://en.wikipedia.org/wiki/Foo", "en.wikipedia.org_wiki_Foo.html"),
        ("https://example.com/", "example.com.html"),
        ("https://example.com", "example.com.html"),
        ("https://example.com/page.aspx", "example.com_page.html"),
    ],
)
def test_blob_name_for_url_returns_flat_parseable_name(
    url: str, expected: str
) -> None:
    assert _blob_name_for_url(url) == expected


def test_blob_name_for_url_is_deterministic_and_has_no_separators() -> None:
    url = "https://example.com/a/b/c/report.pdf"
    name = _blob_name_for_url(url)
    # Same URL -> same blob name (re-ingest overwrites); flat (no path
    # separators) so it round-trips through `_validate_filename`.
    assert _blob_name_for_url(url) == name
    assert "/" not in name
    assert "\\" not in name


# ---------------------------------------------------------------------------
# ingest_url -- registry dispatch + receipt assembly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_url_downloads_and_uploads_like_a_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service downloads the URL bytes and hands them to
    ``upload_document`` under a deterministic blob filename -- so a
    URL ingests through the same store -> ``batch_push`` pipeline as a
    file upload. The receipt echoes the URL + maps the upload result.
    """
    fake_fetch = AsyncMock(return_value=b"<html>page</html>")
    monkeypatch.setattr(ingestion_module, "fetch_url", fake_fetch)
    receipt = UploadResponse(
        filename="example.com_page.html",
        blob_path="docs/example.com_page.html",
        ingestion_job_id="job-up",
        queued=True,
    )
    fake_upload = AsyncMock(return_value=receipt)
    monkeypatch.setattr(ingestion_module, "upload_document", fake_upload)

    settings = NS()
    credential = MagicMock()
    request = IngestUrlRequest(
        url="https://example.com/page", ingestion_job_id="job-req"
    )
    result = await ingest_url(request, settings=settings, credential=credential)

    fake_fetch.assert_awaited_once_with("https://example.com/page")
    _, up_kwargs = fake_upload.call_args
    assert up_kwargs["filename"] == "example.com_page.html"
    assert up_kwargs["content"] == b"<html>page</html>"
    assert up_kwargs["settings"] is settings
    assert up_kwargs["credential"] is credential
    # Receipt echoes the URL and maps the upload result (no synchronous
    # document_count -- indexing is async, same as file upload).
    assert result.url == "https://example.com/page"
    assert result.filename == "example.com_page.html"
    assert result.blob_path == "docs/example.com_page.html"
    assert result.ingestion_job_id == "job-up"
    assert result.queued is True


@pytest.mark.asyncio
async def test_ingest_url_propagates_fetch_error_without_uploading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fetch failure propagates and the blob is never written --
    the route's app-level handler maps ``httpx.HTTPError`` to 502.
    """
    monkeypatch.setattr(
        ingestion_module,
        "fetch_url",
        AsyncMock(side_effect=httpx.HTTPError("dead host")),
    )
    fake_upload = AsyncMock()
    monkeypatch.setattr(ingestion_module, "upload_document", fake_upload)

    request = IngestUrlRequest(url="https://example.com/x.pdf")
    with pytest.raises(httpx.HTTPError):
        await ingest_url(request, settings=NS(), credential=MagicMock())
    fake_upload.assert_not_awaited()


# ---------------------------------------------------------------------------
# upload_document -- blob upload + push-queue enqueue
# ---------------------------------------------------------------------------


def _settings_stub(
    *,
    documents_container: str = "docs",
    doc_processing_queue: str = "doc-processing",
    storage_account_name: str = "stg",
    storage_blob_endpoint: str = "",
    ingestion_trigger: IngestionTrigger = IngestionTrigger.DIRECT_ENQUEUE,
) -> Any:
    """Settings stub shaped for ``upload_document``."""
    return NS(
        storage=NS(
            documents_container=documents_container,
            doc_processing_queue=doc_processing_queue,
            storage_account_name=storage_account_name,
            storage_blob_endpoint=storage_blob_endpoint,
            ingestion_trigger=ingestion_trigger,
        )
    )


def _patch_storage_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AsyncMock, AsyncMock, dict[str, Any]]:
    """Patch ``storage_clients`` with an async context manager yielding
    mock ``(container_client, queue_client)`` pair. Returns the two
    mocks plus a ``captured`` dict carrying the kwargs the helper was
    called with so tests can assert wire shape.
    """
    container_client = AsyncMock(name="container_client")
    queue_client = AsyncMock(name="queue_client")
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_storage_clients(**kwargs: Any):
        captured["kwargs"] = kwargs
        yield container_client, queue_client

    monkeypatch.setattr(ingestion_module, "storage_clients", fake_storage_clients)
    return container_client, queue_client, captured


@pytest.mark.asyncio
async def test_upload_document_uploads_blob_and_enqueues_push(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-step happy path: upload bytes to the documents container,
    then enqueue a ``BatchPushQueueMessage`` carrying the same
    container + filename + correlation id.
    """
    container_client, queue_client, captured = _patch_storage_clients(monkeypatch)
    fake_enqueue = AsyncMock()
    monkeypatch.setattr(ingestion_module, "enqueue_push_message", fake_enqueue)

    settings = _settings_stub()
    credential = MagicMock(name="credential")
    response = await upload_document(
        filename="report.pdf",
        content=b"hello world",
        settings=settings,
        credential=credential,
    )

    # Storage clients opened against the configured container + queue.
    assert captured["kwargs"]["container_name"] == "docs"
    assert captured["kwargs"]["queue_name"] == "doc-processing"
    assert captured["kwargs"]["credential"] is credential

    # Blob uploaded with overwrite=True so retries replace cleanly.
    container_client.upload_blob.assert_awaited_once_with(
        name="report.pdf", data=b"hello world", overwrite=True
    )

    # Push envelope enqueued onto the queue_client with the right shape.
    fake_enqueue.assert_awaited_once()
    enqueue_args, _ = fake_enqueue.call_args
    forwarded_queue, message = enqueue_args
    assert forwarded_queue is queue_client
    assert isinstance(message, BatchPushQueueMessage)
    assert message.container_name == "docs"
    assert message.filename == "report.pdf"
    # The correlation id flows from the service through the message AND
    # into the response so the FE can join logs end-to-end.
    assert message.ingestion_job_id == response.ingestion_job_id

    # Receipt shape.
    assert response.filename == "report.pdf"
    assert response.blob_path == "docs/report.pdf"
    assert response.queued is True


@pytest.mark.asyncio
async def test_upload_document_event_grid_trigger_uploads_blob_without_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``ingestion_trigger=EVENT_GRID`` the blob is written but no
    push envelope is enqueued -- a storage Event Grid subscription drives
    ingestion instead, so a backend-side enqueue would double-ingest.
    The receipt reports ``queued=False`` per the field's defined meaning.
    """
    container_client, _queue_client, _captured = _patch_storage_clients(monkeypatch)
    fake_enqueue = AsyncMock()
    monkeypatch.setattr(ingestion_module, "enqueue_push_message", fake_enqueue)

    response = await upload_document(
        filename="report.pdf",
        content=b"hello world",
        settings=_settings_stub(ingestion_trigger=IngestionTrigger.EVENT_GRID),
        credential=MagicMock(),
    )

    # Blob still written (Event Grid keys off the BlobCreated event).
    container_client.upload_blob.assert_awaited_once_with(
        name="report.pdf", data=b"hello world", overwrite=True
    )
    # Backend did NOT enqueue -- Event Grid -> blob-events -> blob_event
    # owns the push.
    fake_enqueue.assert_not_called()
    assert response.queued is False
    assert response.blob_path == "docs/report.pdf"
    assert response.filename == "report.pdf"


@pytest.mark.asyncio
async def test_upload_document_does_not_enqueue_when_upload_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blob upload raising ``AzureError`` -> structured log + re-raise
    per Hard Rule #14. The push envelope MUST NOT be enqueued -- a
    push for a blob that isn't actually in the container would tell
    ``batch_push`` to fetch a non-existent file.
    """
    container_client, _queue_client, _captured = _patch_storage_clients(monkeypatch)
    container_client.upload_blob.side_effect = AzureError("blob storage down")
    fake_enqueue = AsyncMock()
    monkeypatch.setattr(ingestion_module, "enqueue_push_message", fake_enqueue)

    with pytest.raises(AzureError, match="blob storage down"):
        await upload_document(
            filename="report.pdf",
            content=b"x",
            settings=_settings_stub(),
            credential=MagicMock(),
        )
    fake_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_upload_document_propagates_enqueue_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue enqueue failing -> exception propagates (the helper logs
    the SDK boundary inside ``enqueue_push_message``; this layer
    doesn't double-wrap).
    """
    container_client, _queue_client, _captured = _patch_storage_clients(monkeypatch)
    fake_enqueue = AsyncMock(side_effect=AzureError("queue down"))
    monkeypatch.setattr(ingestion_module, "enqueue_push_message", fake_enqueue)

    with pytest.raises(AzureError, match="queue down"):
        await upload_document(
            filename="report.pdf",
            content=b"x",
            settings=_settings_stub(),
            credential=MagicMock(),
        )
    container_client.upload_blob.assert_awaited_once()


# ---------------------------------------------------------------------------
# reprocess_all -- fan-out delegation to batch_start_handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reprocess_all_delegates_to_batch_start_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: opens storage clients against the configured
    container + queue, calls ``batch_start_handler`` with the
    container_name, and surfaces the resulting envelopes' shared
    job id + count in the receipt.
    """
    container_client, queue_client, captured = _patch_storage_clients(monkeypatch)
    enqueued = [
        BatchPushQueueMessage(
            container_name="docs", filename=f"f{i}.pdf", ingestion_job_id="job-rp-1"
        )
        for i in range(3)
    ]
    fake_handler = AsyncMock(return_value=enqueued)
    monkeypatch.setattr(ingestion_module, "batch_start_handler", fake_handler)

    settings = _settings_stub()
    credential = MagicMock(name="credential")
    response = await reprocess_all(settings=settings, credential=credential)

    # Storage clients opened against the configured container + queue.
    assert captured["kwargs"]["container_name"] == "docs"
    assert captured["kwargs"]["queue_name"] == "doc-processing"
    assert captured["kwargs"]["credential"] is credential

    # Handler invoked with a BatchStartRequest for the documents container
    # and the open (container, queue) clients -- proves we share the
    # Functions-tier orchestration verbatim.
    fake_handler.assert_awaited_once()
    args, _ = fake_handler.call_args
    forwarded_request, forwarded_container, forwarded_queue = args
    assert isinstance(forwarded_request, BatchStartRequest)
    assert forwarded_request.container_name == "docs"
    assert forwarded_request.prefix is None
    assert forwarded_request.force_reindex is False
    assert forwarded_container is container_client
    assert forwarded_queue is queue_client

    # Receipt shape mirrors the Functions HTTP response.
    assert response.ingestion_job_id == "job-rp-1"
    assert response.enqueued_count == 3


@pytest.mark.asyncio
async def test_reprocess_all_returns_none_job_id_for_empty_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty container -> ``ingestion_job_id=None`` so the FE can
    distinguish "nothing to do" from "queued N items".
    """
    _patch_storage_clients(monkeypatch)
    monkeypatch.setattr(
        ingestion_module, "batch_start_handler", AsyncMock(return_value=[])
    )

    response = await reprocess_all(
        settings=_settings_stub(), credential=MagicMock()
    )
    assert response.ingestion_job_id is None
    assert response.enqueued_count == 0


@pytest.mark.asyncio
async def test_reprocess_all_propagates_azure_error_from_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``AzureError`` from the handler (blob list / queue send) bubbles
    up unchanged -- the handler logs the SDK boundary, so this layer
    doesn't double-wrap.
    """
    _patch_storage_clients(monkeypatch)
    monkeypatch.setattr(
        ingestion_module,
        "batch_start_handler",
        AsyncMock(side_effect=AzureError("storage down")),
    )
    with pytest.raises(AzureError, match="storage down"):
        await reprocess_all(
            settings=_settings_stub(), credential=MagicMock()
        )


# ---------------------------------------------------------------------------
# validate_upload -- pre-ingest validation gate (raises UploadRejected)
# ---------------------------------------------------------------------------


def _upload_settings(
    *,
    documents_container: str = "docs",
    doc_processing_queue: str = "doc-processing",
    services_endpoint: str = "https://ai.example.com/",
) -> Any:
    """Settings stub shaped for ``validate_upload`` (storage + foundry)."""
    return NS(
        storage=NS(
            documents_container=documents_container,
            doc_processing_queue=doc_processing_queue,
        ),
        foundry=NS(services_endpoint=services_endpoint),
    )


def test_validate_upload_accepts_local_parser_without_ai_services() -> None:
    # A txt file parses locally, so it passes even with no AI Services
    # endpoint configured.
    validate_upload(
        "notes.txt", 10, settings=_upload_settings(services_endpoint="")
    )


def test_validate_upload_accepts_di_file_when_ai_services_configured() -> None:
    validate_upload("report.pdf", 10, settings=_upload_settings())


def test_validate_upload_rejects_when_storage_unconfigured() -> None:
    with pytest.raises(UploadRejected) as exc:
        validate_upload(
            "notes.txt", 10, settings=_upload_settings(documents_container="")
        )
    assert exc.value.status_code == 503


def test_validate_upload_rejects_empty_filename() -> None:
    with pytest.raises(UploadRejected) as exc:
        validate_upload("", 10, settings=_upload_settings())
    assert exc.value.status_code == 422


def test_validate_upload_rejects_unsupported_extension() -> None:
    with pytest.raises(UploadRejected) as exc:
        validate_upload("data.xyz", 10, settings=_upload_settings())
    assert exc.value.status_code == 415
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["extension"] == "xyz"
    # The supported set is sourced from the registry (the authoritative
    # supported-file-type list), serialized as bare extensions.
    assert "pdf" in exc.value.detail["supported"]


def test_validate_upload_rejects_extensionless_filename() -> None:
    with pytest.raises(UploadRejected) as exc:
        validate_upload("README", 10, settings=_upload_settings())
    assert exc.value.status_code == 415


@pytest.mark.parametrize("filename", ["report.pdf", "memo.docx", "scan.png"])
def test_validate_upload_rejects_di_file_when_ai_services_missing(
    filename: str,
) -> None:
    # A Document-Intelligence-routed file with no https AI Services
    # endpoint is refused (the parse step would poison every queued
    # message) -- driven by the parser's requires_ai_services flag, not a
    # hard-coded extension set.
    with pytest.raises(UploadRejected) as exc:
        validate_upload(filename, 10, settings=_upload_settings(services_endpoint=""))
    assert exc.value.status_code == 503


def test_validate_upload_rejects_oversized_content() -> None:
    with pytest.raises(UploadRejected) as exc:
        validate_upload(
            "big.txt", MAX_UPLOAD_SIZE_BYTES + 1, settings=_upload_settings()
        )
    assert exc.value.status_code == 413
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["max_byte_count"] == MAX_UPLOAD_SIZE_BYTES


def test_validate_upload_accepts_content_at_the_limit() -> None:
    # Exactly the cap is allowed; only strictly-over is rejected.
    validate_upload(
        "big.txt", MAX_UPLOAD_SIZE_BYTES, settings=_upload_settings()
    )
