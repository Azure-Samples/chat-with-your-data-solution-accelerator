"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/batch_start/handler.py."""

from collections.abc import AsyncIterator
from typing import cast

import pytest
from azure.storage.blob.aio import ContainerClient
from azure.storage.queue.aio import QueueClient

from functions.batch_start.handler import batch_start_handler
from functions.batch_start.models import BatchStartRequest
from functions.core.contracts import BatchPushQueueMessage


class _FakeContainerClient:
    """Minimal async stand-in mirroring the surface used by ``list_blobs``."""

    def __init__(self, *, names: list[str], container_name: str = "documents") -> None:
        self.container_name = container_name
        self._names = names
        self.observed_prefix: str | None | object = object()  # sentinel

    def list_blob_names(
        self, name_starts_with: str | None = None
    ) -> AsyncIterator[str]:
        self.observed_prefix = name_starts_with

        async def _gen() -> AsyncIterator[str]:
            for n in self._names:
                yield n

        return _gen()


class _FakeQueueClient:
    """Minimal async stand-in mirroring the surface used by ``enqueue_push_message``."""

    def __init__(self, *, queue_name: str = "doc-processing") -> None:
        self.queue_name = queue_name
        self.sent: list[str] = []

    async def send_message(self, content: str) -> None:
        self.sent.append(content)


def _as_container(fake: _FakeContainerClient) -> ContainerClient:
    return cast(ContainerClient, fake)


def _as_queue(fake: _FakeQueueClient) -> QueueClient:
    return cast(QueueClient, fake)


@pytest.mark.asyncio
async def test_fans_out_one_message_per_blob() -> None:
    container = _FakeContainerClient(names=["a.pdf", "b.pdf", "c.pdf"])
    queue = _FakeQueueClient()
    request = BatchStartRequest(container_name="documents")

    result = await batch_start_handler(request, _as_container(container), _as_queue(queue))

    assert len(result) == 3
    assert [m.filename for m in result] == ["a.pdf", "b.pdf", "c.pdf"]
    assert len(queue.sent) == 3
    # Bodies on the wire round-trip to the same envelopes.
    rebuilt = [BatchPushQueueMessage.model_validate_json(b) for b in queue.sent]
    assert rebuilt == result


@pytest.mark.asyncio
async def test_empty_container_enqueues_nothing() -> None:
    container = _FakeContainerClient(names=[])
    queue = _FakeQueueClient()
    request = BatchStartRequest(container_name="documents")

    result = await batch_start_handler(request, _as_container(container), _as_queue(queue))

    assert result == []
    assert queue.sent == []


@pytest.mark.asyncio
async def test_prefix_is_forwarded_to_list_blobs() -> None:
    container = _FakeContainerClient(names=["2026/x.pdf"])
    queue = _FakeQueueClient()
    request = BatchStartRequest(container_name="documents", prefix="2026/")

    await batch_start_handler(request, _as_container(container), _as_queue(queue))

    assert container.observed_prefix == "2026/"


@pytest.mark.asyncio
async def test_force_reindex_is_propagated_into_every_message() -> None:
    container = _FakeContainerClient(names=["a.pdf", "b.pdf"])
    queue = _FakeQueueClient()
    request = BatchStartRequest(container_name="documents", force_reindex=True)

    result = await batch_start_handler(request, _as_container(container), _as_queue(queue))

    assert all(m.force_reindex is True for m in result)


@pytest.mark.asyncio
async def test_all_messages_share_one_ingestion_job_id() -> None:
    container = _FakeContainerClient(names=["a.pdf", "b.pdf", "c.pdf"])
    queue = _FakeQueueClient()
    request = BatchStartRequest(container_name="documents")

    result = await batch_start_handler(request, _as_container(container), _as_queue(queue))

    job_ids = {m.ingestion_job_id for m in result}
    assert len(job_ids) == 1
    # Sanity: not an empty string.
    assert next(iter(job_ids))
