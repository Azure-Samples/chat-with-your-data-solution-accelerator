"""Pure orchestration handler for the ``batch_start`` blueprint.

``batch_start_handler`` composes the units --
:func:`functions.batch_start.blob_listing.list_blobs` and
:func:`functions.batch_start.queue_writer.enqueue_push_message` -- into
the fan-out step: list blobs under a prefix, emit one
:class:`BatchPushQueueMessage` per blob onto the push queue.

Design notes:

* The handler accepts the ``ContainerClient`` and ``QueueClient`` as
  parameters (treat as DI). Credentials wiring, account URLs, and the
  HTTP / Functions binding live in the function_app.py blueprint
  registration. Keeping the handler client-injected makes
  it directly unit-testable without spinning up Azurite.
* All blobs in one ``batch_start`` invocation share a single
  ``ingestion_job_id`` so downstream traces / search-index documents
  for one fan-out are correlatable end-to-end. Each per-blob queue
  message still gets its own envelope (one filename per envelope --
  ``batch_push`` is a 1:1 consumer).
* No try/except wrapper here. ``list_blobs`` and
  ``enqueue_push_message`` already wrap their SDK boundaries per
  [v2/docs/exception_handling_policy.md] section "Functions
  blueprints". Adding another layer would double-log. An exception
  from either propagates so the Functions runtime applies its retry
  policy.
* Sequential ``await`` per message (no ``asyncio.gather``) is
  intentional: ordering matters for traceability and the storage
  queue SDK does not benefit from in-flight parallelism at typical
  ingestion sizes. Revisit only with a measured hot path.
"""

from uuid import uuid4

from azure.storage.blob.aio import ContainerClient
from azure.storage.queue.aio import QueueClient

from functions.batch_start.blob_listing import list_blobs
from functions.batch_start.models import BatchStartRequest
from functions.batch_start.queue_writer import enqueue_push_message
from functions.core.contracts import BatchPushQueueMessage


async def batch_start_handler(
    request: BatchStartRequest,
    container_client: ContainerClient,
    queue_client: QueueClient,
) -> list[BatchPushQueueMessage]:
    """Fan out blobs under ``request.prefix`` as push-queue messages.

    Returns the list of envelopes enqueued (in the same order blobs
    were listed) so the HTTP wrapper can include them in its response
    body for traceability.
    """
    blob_names = await list_blobs(container_client, prefix=request.prefix)
    ingestion_job_id = str(uuid4())
    messages = [
        BatchPushQueueMessage(
            container_name=request.container_name,
            filename=name,
            ingestion_job_id=ingestion_job_id,
            force_reindex=request.force_reindex,
        )
        for name in blob_names
    ]
    for message in messages:
        await enqueue_push_message(queue_client, message)
    return messages
