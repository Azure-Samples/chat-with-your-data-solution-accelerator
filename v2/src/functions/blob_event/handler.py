"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Handler for the ``blob_event`` blueprint.

Bridges an Event Grid ``BlobCreated`` event to the existing ingestion
pipeline: parse the event subject into a container + blob reference
(skipping non-blob / malformed subjects), build the CWYD ingestion
envelope (:class:`BatchPushQueueMessage`), and enqueue it onto the
doc-processing queue where the unchanged ``batch_push`` consumer runs
the parse / embed / push pipeline. This reuses the existing producer
(:func:`functions.batch_start.queue_writer.enqueue_push_message`) and
consumer rather than duplicating ingestion logic.

A fresh ``ingestion_job_id`` is minted per event (the envelope's
default factory), so each blob write becomes its own correlatable
job. ``force_reindex`` is ``False``: a re-upload overwrites the same
blob and re-ingests, and ``batch_push`` upserts on document id, so the
result is idempotent without forcing a re-index flag.
"""

from azure.storage.queue.aio import QueueClient

from functions.batch_start.queue_writer import enqueue_push_message
from functions.blob_event.event_parser import parse_blob_created_subject
from functions.core.contracts import BatchPushQueueMessage


async def blob_event_handler(
    subject: str,
    queue_client: QueueClient,
) -> BatchPushQueueMessage | None:
    """Translate a ``BlobCreated`` event subject into an ingestion job.

    Parses ``subject`` (a non-blob / container-level / malformed
    subject yields ``None`` -> skip), builds a
    :class:`BatchPushQueueMessage` with a fresh ``ingestion_job_id``
    and ``force_reindex=False``, and enqueues it on ``queue_client``
    (the doc-processing queue) for the unchanged ``batch_push``
    consumer. Returns the enqueued envelope, or ``None`` when the
    subject was skipped.

    Caller owns ``queue_client`` lifecycle (DI), mirroring
    :func:`functions.batch_start.queue_writer.enqueue_push_message`,
    which also owns the ``AzureError`` SDK send boundary (Hard Rule
    #14) -- so this handler adds no try/except.
    """
    ref = parse_blob_created_subject(subject)
    if ref is None:
        return None
    message = BatchPushQueueMessage(
        container_name=ref.container_name,
        filename=ref.filename,
        force_reindex=False,
    )
    await enqueue_push_message(queue_client, message)
    return message
