"""Tests for ``backend.services.ingestion``.

Pillar: Stable Core
Phase: 7 (Testing + Documentation -- admin-side ingestion helpers)
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace as NS
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import AzureError

import backend.services.ingestion as ingestion_module
from backend.models.admin import IngestUrlRequest
from backend.services.ingestion import (
    _parser_key_for_url,
    ingest_url,
    reprocess_all,
    upload_document,
)
from functions.add_url.handler import AddUrlRequest
from functions.batch_start.models import BatchStartRequest
from functions.core.contracts import BatchPushQueueMessage


# ---------------------------------------------------------------------------
# _parser_key_for_url -- registry key resolution from URL path extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com/report.pdf", "pdf"),
        ("https://example.com/path/notes.DOCX", "docx"),
        ("https://example.com/article.html", "html"),
        ("https://example.com/data.json", "json"),
        # Ext-less URL falls back to txt parser.
        ("https://example.com/article", "txt"),
        ("https://example.com/", "txt"),
        # Query string + fragment are stripped from suffix detection.
        ("https://example.com/file.md?ref=x#top", "md"),
    ],
)
def test_parser_key_for_url_returns_expected_registry_key(
    url: str, expected: str
) -> None:
    assert _parser_key_for_url(url) == expected


# ---------------------------------------------------------------------------
# ingest_url -- registry dispatch + receipt assembly
# ---------------------------------------------------------------------------


def _build_collaborators(
    *,
    document_count: int = 3,
):
    """Build mocked parser / embedder registry seams + a search provider.

    Returns ``(parser_cls, embedder_cls, search_provider,
    add_url_handler)`` so each test can patch the module-level
    registry + delegate seams without colliding.
    """
    parser = MagicMock(name="parser_instance")
    parser_cls = MagicMock(name="parser_cls", return_value=parser)
    embedder = MagicMock(name="embedder_instance")
    embedder.aclose = AsyncMock()
    embedder_cls = MagicMock(name="embedder_cls", return_value=embedder)
    search_provider = AsyncMock(name="search_provider")
    documents = [MagicMock(name=f"doc-{i}") for i in range(document_count)]
    add_url_handler = AsyncMock(return_value=documents)
    return parser_cls, embedder_cls, search_provider, add_url_handler


@pytest.mark.asyncio
async def test_ingest_url_dispatches_parser_via_url_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service must resolve the parser registry entry keyed by the
    URL's path extension -- registry-only dispatch (Hard Rule #4),
    no ``if/elif`` on URL shape.
    """
    parser_cls, embedder_cls, search_provider, fake_handler = _build_collaborators()
    parser_registry = MagicMock()
    parser_registry.get = MagicMock(return_value=parser_cls)
    embedder_registry = MagicMock()
    embedder_registry.get = MagicMock(return_value=embedder_cls)
    monkeypatch.setattr(
        ingestion_module.ingestion_parsers_registry,
        "registry",
        parser_registry,
    )
    monkeypatch.setattr(
        ingestion_module.embedders_registry, "registry", embedder_registry
    )
    monkeypatch.setattr(ingestion_module, "add_url_handler", fake_handler)

    settings = NS()
    credential = MagicMock()
    request = IngestUrlRequest(
        url="https://example.com/report.pdf", ingestion_job_id="job-1"
    )

    await ingest_url(
        request,
        settings=settings,
        credential=credential,
        search_provider=search_provider,
    )

    parser_registry.get.assert_called_once_with("pdf")
    parser_cls.assert_called_once_with(settings=settings, credential=credential)
    embedder_registry.get.assert_called_once_with("azure_openai")
    embedder_cls.assert_called_once_with(settings=settings, credential=credential)


@pytest.mark.asyncio
async def test_ingest_url_returns_typed_response_with_document_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Receipt carries the correlation id, echoed URL, and pushed
    chunk count. Count comes from the length of the document list
    returned by ``add_url_handler`` -- the handler is the authority
    on what landed in the index.
    """
    parser_cls, embedder_cls, search_provider, fake_handler = _build_collaborators(
        document_count=5
    )
    monkeypatch.setattr(
        ingestion_module.ingestion_parsers_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=parser_cls)),
    )
    monkeypatch.setattr(
        ingestion_module.embedders_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=embedder_cls)),
    )
    monkeypatch.setattr(ingestion_module, "add_url_handler", fake_handler)

    request = IngestUrlRequest(
        url="https://example.com/notes.md", ingestion_job_id="job-xyz"
    )
    result = await ingest_url(
        request,
        settings=NS(),
        credential=MagicMock(),
        search_provider=search_provider,
    )

    assert result.ingestion_job_id == "job-xyz"
    assert result.url == "https://example.com/notes.md"
    assert result.document_count == 5


@pytest.mark.asyncio
async def test_ingest_url_closes_embedder_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedder is built per-request and MUST be closed even on the
    success path -- mirrors the discipline in
    :mod:`functions.add_url.blueprint._execute`.
    """
    parser_cls, embedder_cls, search_provider, fake_handler = _build_collaborators()
    monkeypatch.setattr(
        ingestion_module.ingestion_parsers_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=parser_cls)),
    )
    monkeypatch.setattr(
        ingestion_module.embedders_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=embedder_cls)),
    )
    monkeypatch.setattr(ingestion_module, "add_url_handler", fake_handler)

    embedder_instance = embedder_cls.return_value
    request = IngestUrlRequest(
        url="https://example.com/a.pdf", ingestion_job_id="job-1"
    )
    await ingest_url(
        request,
        settings=NS(),
        credential=MagicMock(),
        search_provider=search_provider,
    )
    embedder_instance.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_url_closes_embedder_on_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedder is closed even when ``add_url_handler`` raises --
    the ``finally`` block must run before the exception propagates
    so a fetch / embed / push failure doesn't leak the embedder's
    async client.
    """
    parser_cls, embedder_cls, search_provider, _ = _build_collaborators()
    boom = AsyncMock(side_effect=RuntimeError("upstream failure"))
    monkeypatch.setattr(
        ingestion_module.ingestion_parsers_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=parser_cls)),
    )
    monkeypatch.setattr(
        ingestion_module.embedders_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=embedder_cls)),
    )
    monkeypatch.setattr(ingestion_module, "add_url_handler", boom)

    embedder_instance = embedder_cls.return_value
    request = IngestUrlRequest(
        url="https://example.com/a.pdf", ingestion_job_id="job-1"
    )
    with pytest.raises(RuntimeError, match="upstream failure"):
        await ingest_url(
            request,
            settings=NS(),
            credential=MagicMock(),
            search_provider=search_provider,
        )
    embedder_instance.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_url_forwards_request_and_search_to_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service delegates to ``add_url_handler`` with the
    Functions-tier ``AddUrlRequest`` carrying the same URL +
    correlation id, plus the lifespan-cached search provider --
    proves the two ingestion paths share one orchestration pipeline.
    """
    parser_cls, embedder_cls, search_provider, fake_handler = _build_collaborators()
    monkeypatch.setattr(
        ingestion_module.ingestion_parsers_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=parser_cls)),
    )
    monkeypatch.setattr(
        ingestion_module.embedders_registry,
        "registry",
        MagicMock(get=MagicMock(return_value=embedder_cls)),
    )
    monkeypatch.setattr(ingestion_module, "add_url_handler", fake_handler)

    request = IngestUrlRequest(
        url="https://example.com/x.pdf", ingestion_job_id="job-99"
    )
    await ingest_url(
        request,
        settings=NS(),
        credential=MagicMock(),
        search_provider=search_provider,
    )

    args, _ = fake_handler.call_args
    forwarded_request, forwarded_parser, forwarded_embedder, forwarded_search = args
    assert isinstance(forwarded_request, AddUrlRequest)
    assert forwarded_request.url == "https://example.com/x.pdf"
    assert forwarded_request.ingestion_job_id == "job-99"
    assert forwarded_parser is parser_cls.return_value
    assert forwarded_embedder is embedder_cls.return_value
    assert forwarded_search is search_provider


# ---------------------------------------------------------------------------
# upload_document -- blob upload + push-queue enqueue
# ---------------------------------------------------------------------------


def _settings_stub(
    *,
    documents_container: str = "docs",
    doc_processing_queue: str = "doc-processing",
    storage_account_name: str = "stg",
    storage_blob_endpoint: str = "",
) -> Any:
    """Settings stub shaped for ``upload_document``."""
    return NS(
        storage=NS(
            documents_container=documents_container,
            doc_processing_queue=doc_processing_queue,
            storage_account_name=storage_account_name,
            storage_blob_endpoint=storage_blob_endpoint,
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
