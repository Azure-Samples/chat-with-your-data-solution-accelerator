"""Tests for src/functions/batch_start/queue_writer.py."""

import logging
from typing import cast

import pytest
from azure.core.exceptions import AzureError
from azure.storage.queue.aio import QueueClient

from functions.batch_start.queue_writer import enqueue_push_message
from functions.core.contracts import BatchPushQueueMessage


class _FakeQueueClient:
    """Minimal async stand-in for ``azure.storage.queue.aio.QueueClient``.

    Only the attrs/methods touched by ``enqueue_push_message`` are
    modeled: ``queue_name`` (used in the error log) and
    ``send_message`` (the SDK call).
    """

    def __init__(
        self,
        *,
        queue_name: str = "doc-processing",
        raises: AzureError | None = None,
    ) -> None:
        self.queue_name = queue_name
        self._raises = raises
        self.sent: list[str] = []

    async def send_message(self, content: str) -> None:
        if self._raises is not None:
            raise self._raises
        self.sent.append(content)


def _as_queue(fake: _FakeQueueClient) -> QueueClient:
    return cast(QueueClient, fake)


@pytest.mark.asyncio
async def test_send_message_serializes_envelope_as_json() -> None:
    fake = _FakeQueueClient()
    msg = BatchPushQueueMessage(
        container_name="documents",
        filename="2026/contract.pdf",
        ingestion_job_id="job-abc",
        force_reindex=True,
    )
    await enqueue_push_message(_as_queue(fake), msg)
    assert len(fake.sent) == 1
    # Round-trip the body to prove it's the canonical JSON envelope.
    rebuilt = BatchPushQueueMessage.model_validate_json(fake.sent[0])
    assert rebuilt == msg


@pytest.mark.asyncio
async def test_returns_none() -> None:
    fake = _FakeQueueClient()
    msg = BatchPushQueueMessage(container_name="c", filename="f.pdf")
    result = await enqueue_push_message(_as_queue(fake), msg)
    assert result is None


@pytest.mark.asyncio
async def test_multiple_sends_each_succeed() -> None:
    fake = _FakeQueueClient()
    a = BatchPushQueueMessage(container_name="c", filename="a.pdf")
    b = BatchPushQueueMessage(container_name="c", filename="b.pdf")
    await enqueue_push_message(_as_queue(fake), a)
    await enqueue_push_message(_as_queue(fake), b)
    assert len(fake.sent) == 2
    assert BatchPushQueueMessage.model_validate_json(fake.sent[0]).filename == "a.pdf"
    assert BatchPushQueueMessage.model_validate_json(fake.sent[1]).filename == "b.pdf"


@pytest.mark.asyncio
async def test_azure_error_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeQueueClient(queue_name="doc-processing", raises=AzureError("boom"))
    msg = BatchPushQueueMessage(
        container_name="documents",
        filename="x.pdf",
        ingestion_job_id="job-zzz",
    )
    caplog.set_level(logging.ERROR, logger="functions.batch_start.queue_writer")
    with pytest.raises(AzureError):
        await enqueue_push_message(_as_queue(fake), msg)
    record = next(r for r in caplog.records if r.message == "queue send_message failed")
    assert record.levelno == logging.ERROR
    assert record.operation == "send_message"  # type: ignore[attr-defined]
    assert record.queue == "doc-processing"  # type: ignore[attr-defined]
    assert record.ingestion_job_id == "job-zzz"  # type: ignore[attr-defined]
    assert record.container == "documents"  # type: ignore[attr-defined]
    assert record.blob_filename == "x.pdf"  # type: ignore[attr-defined]
