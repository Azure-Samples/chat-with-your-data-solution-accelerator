"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/blob_event/handler.py."""

from typing import cast

import pytest
from azure.storage.queue.aio import QueueClient

from functions.blob_event.handler import blob_event_handler
from functions.core.contracts import BatchPushQueueMessage

_DOCUMENTS_SUBJECT = (
    "/blobServices/default/containers/documents/blobs/Benefit_Options.pdf"
)


class _FakeQueueClient:
    """Minimal async stand-in for ``azure.storage.queue.aio.QueueClient``.

    Only the attrs ``enqueue_push_message`` touches are modeled:
    ``queue_name`` (error log) and ``send_message`` (the SDK call).
    """

    def __init__(self, *, queue_name: str = "doc-processing") -> None:
        self.queue_name = queue_name
        self.sent: list[str] = []

    async def send_message(self, content: str) -> None:
        self.sent.append(content)


def _as_queue(fake: _FakeQueueClient) -> QueueClient:
    return cast(QueueClient, fake)


@pytest.mark.asyncio
async def test_enqueues_envelope_for_blob_subject() -> None:
    fake = _FakeQueueClient()
    result = await blob_event_handler(_DOCUMENTS_SUBJECT, _as_queue(fake))

    assert result is not None
    assert result.container_name == "documents"
    assert result.filename == "Benefit_Options.pdf"
    # Event Grid path never force-reindexes; batch_push upserts on id.
    assert result.force_reindex is False
    # A fresh correlation id is minted per event.
    assert result.ingestion_job_id

    # Exactly one message enqueued, and it round-trips to the returned envelope.
    assert len(fake.sent) == 1
    assert BatchPushQueueMessage.model_validate_json(fake.sent[0]) == result


@pytest.mark.asyncio
async def test_captures_virtual_directory_path() -> None:
    subject = "/blobServices/default/containers/documents/blobs/2026/q1/report.pdf"
    fake = _FakeQueueClient()
    result = await blob_event_handler(subject, _as_queue(fake))

    assert result is not None
    assert result.filename == "2026/q1/report.pdf"


@pytest.mark.asyncio
async def test_skips_non_blob_subject_without_enqueueing() -> None:
    fake = _FakeQueueClient()
    result = await blob_event_handler(
        "/blobServices/default/containers/documents", _as_queue(fake)
    )

    assert result is None
    assert fake.sent == []


@pytest.mark.asyncio
async def test_mints_distinct_job_ids_per_event() -> None:
    fake = _FakeQueueClient()
    first = await blob_event_handler(_DOCUMENTS_SUBJECT, _as_queue(fake))
    second = await blob_event_handler(_DOCUMENTS_SUBJECT, _as_queue(fake))

    assert first is not None
    assert second is not None
    assert first.ingestion_job_id != second.ingestion_job_id
