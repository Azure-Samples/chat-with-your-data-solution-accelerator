"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/blob_event/handler.py."""

from typing import cast

import pytest
from azure.storage.queue.aio import QueueClient
from pydantic import ValidationError

from backend.core.providers.search.base import BaseSearch
from functions.blob_event.event_parser import BlobEventType, ParsedBlobRef
from functions.blob_event.handler import (
    BlobEventOutcome,
    handle_blob_created,
    handle_blob_deleted,
)
from functions.core.contracts import BatchPushQueueMessage

_REF = ParsedBlobRef(container_name="documents", filename="Benefit_Options.pdf")


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


# ---------------------------------------------------------------------------
# handle_blob_created — enqueue an ingestion job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_created_enqueues_envelope_for_blob_ref() -> None:
    fake = _FakeQueueClient()
    outcome = await handle_blob_created(_REF, _as_queue(fake))

    assert outcome.event_type is BlobEventType.CREATED
    assert outcome.filename == "Benefit_Options.pdf"
    assert outcome.deleted_count is None
    message = outcome.enqueued
    assert message is not None
    assert message.container_name == "documents"
    assert message.filename == "Benefit_Options.pdf"
    # Event Grid path never force-reindexes; batch_push upserts on id.
    assert message.force_reindex is False
    # A fresh correlation id is minted per event.
    assert message.ingestion_job_id

    # Exactly one message enqueued, and it round-trips to the envelope.
    assert len(fake.sent) == 1
    assert BatchPushQueueMessage.model_validate_json(fake.sent[0]) == message


@pytest.mark.asyncio
async def test_created_keeps_virtual_directory_path() -> None:
    ref = ParsedBlobRef(container_name="documents", filename="2026/q1/report.pdf")
    fake = _FakeQueueClient()
    outcome = await handle_blob_created(ref, _as_queue(fake))

    assert outcome.enqueued is not None
    assert outcome.enqueued.filename == "2026/q1/report.pdf"


@pytest.mark.asyncio
async def test_created_mints_distinct_job_ids_per_event() -> None:
    fake = _FakeQueueClient()
    first = await handle_blob_created(_REF, _as_queue(fake))
    second = await handle_blob_created(_REF, _as_queue(fake))

    assert first.enqueued is not None
    assert second.enqueued is not None
    assert first.enqueued.ingestion_job_id != second.enqueued.ingestion_job_id


@pytest.mark.asyncio
async def test_created_outcome_is_frozen() -> None:
    fake = _FakeQueueClient()
    outcome = await handle_blob_created(_REF, _as_queue(fake))
    with pytest.raises(ValidationError):
        outcome.filename = "other.pdf"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# handle_blob_deleted — de-index by source
# ---------------------------------------------------------------------------


class _FakeSearch:
    """Minimal stand-in for ``BaseSearch`` exposing only ``delete_by_source``."""

    def __init__(self, *, deleted: int) -> None:
        self._deleted = deleted
        self.deleted_sources: list[str] = []

    async def delete_by_source(self, source: str) -> int:
        self.deleted_sources.append(source)
        return self._deleted


def _as_search(fake: _FakeSearch) -> BaseSearch:
    # BaseSearch is an ABC; the handler only calls delete_by_source.
    return cast(BaseSearch, fake)


@pytest.mark.asyncio
async def test_deleted_deindexes_by_filename() -> None:
    fake = _FakeSearch(deleted=7)
    outcome = await handle_blob_deleted(_REF, _as_search(fake))

    assert outcome.event_type is BlobEventType.DELETED
    assert outcome.filename == "Benefit_Options.pdf"
    assert outcome.enqueued is None
    assert outcome.deleted_count == 7
    # delete_by_source is keyed on the blob path (the indexed source).
    assert fake.deleted_sources == ["Benefit_Options.pdf"]


@pytest.mark.asyncio
async def test_deleted_zero_count_is_not_an_error() -> None:
    # A delete for a blob that was never indexed is a no-op, not a failure.
    fake = _FakeSearch(deleted=0)
    outcome = await handle_blob_deleted(_REF, _as_search(fake))

    assert outcome.deleted_count == 0
    assert fake.deleted_sources == ["Benefit_Options.pdf"]


@pytest.mark.asyncio
async def test_deleted_keeps_virtual_directory_path() -> None:
    ref = ParsedBlobRef(container_name="documents", filename="2026/q1/report.pdf")
    fake = _FakeSearch(deleted=3)
    outcome = await handle_blob_deleted(ref, _as_search(fake))

    assert outcome.deleted_count == 3
    assert fake.deleted_sources == ["2026/q1/report.pdf"]


def test_outcome_round_trips_through_model() -> None:
    # A CREATED outcome and a DELETED outcome are distinguishable by their
    # discriminator + the populated branch field.
    created = BlobEventOutcome(
        event_type=BlobEventType.CREATED,
        filename="a.pdf",
        enqueued=BatchPushQueueMessage(container_name="documents", filename="a.pdf"),
    )
    deleted = BlobEventOutcome(
        event_type=BlobEventType.DELETED, filename="a.pdf", deleted_count=2
    )
    assert created.deleted_count is None
    assert deleted.enqueued is None
