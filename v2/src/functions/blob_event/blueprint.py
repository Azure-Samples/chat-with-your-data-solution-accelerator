"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Queue-trigger blueprint that turns a ``Microsoft.Storage.BlobCreated``
event into a doc-processing ingestion job, so any blob written to the
documents container -- by a bulk drop, an admin upload, or any other
writer -- is auto-ingested by the unchanged ``batch_push`` consumer.

Wire shape:

* **Trigger** -- ``azure.functions.QueueMessage`` on the ``blob-events``
  queue. The Event Grid system topic on the storage account delivers
  filtered ``BlobCreated`` events (scoped to the documents container) to
  ``blob-events`` (a StorageQueue destination with managed-identity
  delivery). A queue destination -- not an Event Grid ``AzureFunction``
  trigger -- keeps the no-keys managed-identity posture and deploys as
  pure bicep, because the queue exists at provision time (ADR 0028).
* **Translate + reuse** -- the body delegates to
  :func:`functions.blob_event.event_parser.subject_from_event_message`
  (raw Event Grid event -> blob subject) then
  :func:`functions.blob_event.handler.blob_event_handler` (subject ->
  :class:`BatchPushQueueMessage` -> ``enqueue_push_message`` onto
  ``doc-processing``). ``batch_push`` consumes ``doc-processing``
  unchanged.
* **Failure mode** -- :func:`functions.core.exception_mapping.log_queue_errors`
  logs a structured trail and re-raises so the runtime applies its
  retry -> poison-queue policy.

The ``blob-events`` queue name is a fixed infra constant referenced only
here and by the bicep queue + Event Grid subscription, so it is a
literal rather than a ``%APP_SETTING%`` env-ref -- which avoids a host
binding dependency that would otherwise have to be present in every
``local.settings.json``. Registry-first credential wiring (Hard Rule
#4): the credentials provider is resolved via ``credentials_registry``
exactly as ``batch_push`` does. The private :func:`_execute` helper is
the single seam tests monkeypatch.
"""

import azure.functions as func
from azure.storage.queue.aio import QueueClient

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.settings import AppSettings, get_settings
from functions.blob_event.event_parser import subject_from_event_message
from functions.blob_event.handler import blob_event_handler
from functions.core.contracts import BatchPushQueueMessage
from functions.core.exception_mapping import log_queue_errors
from functions.core.storage_endpoints import resolve_storage_endpoints

bp = func.Blueprint()

# The queue Event Grid delivers BlobCreated events to. Fixed infra
# constant (matches the bicep queue + system-topic subscription); a
# literal avoids a host app-setting binding dependency.
_BLOB_EVENTS_QUEUE = "blob-events"


async def _execute(
    msg: func.QueueMessage, settings: AppSettings
) -> BatchPushQueueMessage | None:
    """Translate one Event Grid message into a doc-processing job.

    Extracts the blob ``subject`` from the raw Event Grid event body
    (a malformed / non-event message yields ``None`` -> skip, before any
    credential or queue client is opened), then opens the
    ``doc-processing`` queue client and dispatches to
    :func:`blob_event_handler`. Extracted from :func:`blob_event` so
    route-level tests monkeypatch this single seam instead of opening a
    real credential / Storage Queue. Returns the enqueued envelope, or
    ``None`` when the message was skipped, so callers can assert on the
    wire shape.
    """
    subject = subject_from_event_message(msg.get_body())
    if subject is None:
        return None
    _blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    async with await cred_provider.get_credential() as credential:
        async with QueueClient(
            account_url=queue_endpoint,
            queue_name=settings.storage.doc_processing_queue,
            credential=credential,
        ) as queue_client:
            return await blob_event_handler(subject, queue_client)


@bp.queue_trigger(
    arg_name="msg",
    queue_name=_BLOB_EVENTS_QUEUE,
    connection="AzureWebJobsStorage",
)
@log_queue_errors("blob_event")
async def blob_event(msg: func.QueueMessage) -> None:
    """Queue trigger -- translate a ``BlobCreated`` event into ingestion.

    Dispatches to :func:`_execute`, which extracts the subject, opens
    the doc-processing queue client, and runs :func:`blob_event_handler`.
    Failures bubble to :func:`log_queue_errors` which logs and re-raises
    so the runtime engages retry -> poison.
    """
    await _execute(msg, get_settings())
