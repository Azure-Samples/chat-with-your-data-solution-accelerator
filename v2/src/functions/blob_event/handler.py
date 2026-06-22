"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Per-event action handlers for the ``blob_event`` blueprint.

Two pure actions, one per blob event the trigger acts on. The blueprint
:func:`functions.blob_event.blueprint._execute` classifies the event and
opens only the collaborator the matched action needs (the queue client
for a create, the search provider for a delete), then calls the matching
handler here:

* :func:`handle_blob_created` -- a blob was written, so build the CWYD
  ingestion envelope (:class:`BatchPushQueueMessage`) and enqueue it on
  the doc-processing queue where the unchanged ``batch_push`` consumer
  runs parse / embed / push. A fresh ``ingestion_job_id`` is minted per
  event (the envelope's default factory) and ``force_reindex`` is
  ``False`` -- a re-upload overwrites the same blob and ``batch_push``
  upserts on document id, so the result is idempotent without forcing a
  re-index flag.
* :func:`handle_blob_deleted` -- a blob was removed, so drop every
  indexed chunk whose source is that blob (``delete_by_source``). The
  blob is already gone from storage; this only de-indexes.

Both return a :class:`BlobEventOutcome` so the blueprint trigger and
tests can assert on what happened. Neither opens an SDK client or owns
an ``AzureError`` boundary -- the collaborators are injected, and their
producers (``enqueue_push_message`` / ``BaseSearch.delete_by_source``)
own the SDK send boundary (Hard Rule #14).
"""

from azure.storage.queue.aio import QueueClient
from pydantic import BaseModel, ConfigDict

from backend.core.providers.search.base import BaseSearch
from functions.batch_start.queue_writer import enqueue_push_message
from functions.blob_event.event_parser import BlobEventType, ParsedBlobRef
from functions.core.contracts import BatchPushQueueMessage


class BlobEventOutcome(BaseModel):
    """What the ``blob_event`` blueprint did with one parsed blob event.

    A discriminated record (``event_type`` is the discriminator) for the
    trigger return + test assertions: ``enqueued`` carries the ingestion
    envelope on a :attr:`BlobEventType.CREATED` event; ``deleted_count``
    carries the number of de-indexed chunks on a
    :attr:`BlobEventType.DELETED` event. The other field stays ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: BlobEventType
    filename: str
    enqueued: BatchPushQueueMessage | None = None
    deleted_count: int | None = None


async def handle_blob_created(
    ref: ParsedBlobRef,
    queue_client: QueueClient,
) -> BlobEventOutcome:
    """Enqueue a doc-processing ingestion job for a newly written blob.

    Builds a :class:`BatchPushQueueMessage` (fresh ``ingestion_job_id``,
    ``force_reindex=False``) for ``ref`` and enqueues it on
    ``queue_client`` (the doc-processing queue) for the unchanged
    ``batch_push`` consumer. ``queue_client`` is caller-owned (DI);
    :func:`functions.batch_start.queue_writer.enqueue_push_message` owns
    the ``AzureError`` send boundary, so this adds no try/except.
    """
    message = BatchPushQueueMessage(
        container_name=ref.container_name,
        filename=ref.filename,
        force_reindex=False,
    )
    await enqueue_push_message(queue_client, message)
    return BlobEventOutcome(
        event_type=BlobEventType.CREATED,
        filename=ref.filename,
        enqueued=message,
    )


async def handle_blob_deleted(
    ref: ParsedBlobRef,
    search: BaseSearch,
) -> BlobEventOutcome:
    """De-index every chunk for a blob that was removed from storage.

    Calls ``search.delete_by_source(ref.filename)`` -- the source stored
    on each chunk is the blob path, the same value ``batch_push`` indexed
    on, so create + delete round-trip on the same key. ``search`` is
    caller-owned (DI) and owns its SDK boundary, so this adds no
    try/except. Returns the deleted-chunk count in the outcome (``0`` when
    the blob was never indexed -- a no-op delete, not an error).
    """
    deleted_count = await search.delete_by_source(ref.filename)
    return BlobEventOutcome(
        event_type=BlobEventType.DELETED,
        filename=ref.filename,
        deleted_count=deleted_count,
    )
