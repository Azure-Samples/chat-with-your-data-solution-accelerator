"""Queue-trigger blueprint that turns a Storage blob event into the right
indexing action: a ``Microsoft.Storage.BlobCreated`` event becomes a
doc-processing ingestion job (auto-ingested by the unchanged
``batch_push`` consumer), and a ``Microsoft.Storage.BlobDeleted`` event
de-indexes the blob's chunks. So any blob written to or removed from the
documents container -- by a bulk drop / delete, an admin upload, or any
other writer -- keeps the index in sync.

Wire shape:

* **Trigger** -- ``azure.functions.QueueMessage`` on the ``blob-events``
  queue. The Event Grid system topic on the storage account delivers
  filtered ``BlobCreated`` / ``BlobDeleted`` events (scoped to the
  documents container) to ``blob-events`` (a StorageQueue destination
  with managed-identity delivery). A queue destination -- not an Event
  Grid ``AzureFunction`` trigger -- keeps the no-keys managed-identity
  posture and deploys as pure bicep, because the queue exists at
  provision time (ADR 0028).
* **Classify + dispatch** -- the body delegates to
  :func:`functions.blob_event.event_parser.parse_blob_event` (raw Event
  Grid event -> typed :class:`ParsedBlobEvent`), then branches on the
  event type: a create calls
  :func:`functions.blob_event.handler.handle_blob_created` (enqueue a
  :class:`BatchPushQueueMessage` onto ``doc-processing``, consumed by the
  unchanged ``batch_push``); a delete resolves the registry-first search
  provider via the shared
  :func:`functions.core.search_resolution.resolve_search_provider`
  (exactly as ``batch_push`` does) and calls
  :func:`functions.blob_event.handler.handle_blob_deleted`
  (``delete_by_source``). Only the collaborator the matched action needs
  is opened.
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
from functions.blob_event.event_parser import BlobEventType, parse_blob_event
from functions.blob_event.handler import (
    BlobEventOutcome,
    handle_blob_created,
    handle_blob_deleted,
)
from functions.core.exception_mapping import log_queue_errors
from functions.core.search_resolution import resolve_search_provider
from functions.core.storage_endpoints import resolve_storage_endpoints

bp = func.Blueprint()

# The queue Event Grid delivers BlobCreated events to. Fixed infra
# constant (matches the bicep queue + system-topic subscription); a
# literal avoids a host app-setting binding dependency.
_BLOB_EVENTS_QUEUE = "blob-events"


async def _execute(
    msg: func.QueueMessage, settings: AppSettings
) -> BlobEventOutcome | None:
    """Classify one Event Grid message and run the matching action.

    Parses the raw event body into a typed :class:`ParsedBlobEvent` (a
    malformed / non-blob / unhandled-type message yields ``None`` -> skip,
    before any credential or SDK client is opened), then branches on the
    event type and opens only the collaborator that branch needs:

    * **create** -- open the ``doc-processing`` queue client and call
      :func:`handle_blob_created` (enqueue an ingestion job).
    * **delete** -- resolve the registry-first search provider via
      :func:`functions.core.search_resolution.resolve_search_provider`
      (the pgvector pool is acquired only on the pgvector path,
      mirroring ``batch_push``) and call :func:`handle_blob_deleted`
      (``delete_by_source``).

    Extracted from :func:`blob_event` so route-level tests monkeypatch
    this single seam instead of opening a real credential / Storage Queue
    / Search service. Returns the :class:`BlobEventOutcome`, or ``None``
    when the message was skipped.
    """
    event = parse_blob_event(msg.get_body())
    if event is None:
        return None
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    async with await cred_provider.get_credential() as credential:
        if event.event_type is BlobEventType.CREATED:
            _blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
            async with QueueClient(
                account_url=queue_endpoint,
                queue_name=settings.storage.doc_processing_queue,
                credential=credential,
            ) as queue_client:
                return await handle_blob_created(event.ref, queue_client)
        # BlobEventType.DELETED -- de-index via the shared
        # functions.core.search_resolution helper (the pgvector pool is
        # acquired only on the pgvector path, mirroring batch_push). The
        # helper runs ensure_schema; this branch owns teardown.
        resolved = await resolve_search_provider(
            settings=settings, credential=credential
        )
        try:
            return await handle_blob_deleted(event.ref, resolved.provider)
        finally:
            await resolved.provider.aclose()
            if resolved.pool_helper is not None:
                await resolved.pool_helper.aclose()


@bp.queue_trigger(
    arg_name="msg",
    queue_name=_BLOB_EVENTS_QUEUE,
    connection="AzureWebJobsStorage",
)
@log_queue_errors("blob_event")
async def blob_event(msg: func.QueueMessage) -> None:
    """Queue trigger -- keep the index in sync with a Storage blob event.

    Dispatches to :func:`_execute`, which classifies the event and runs
    the matching action (create -> enqueue ingestion; delete -> de-index).
    Failures bubble to :func:`log_queue_errors` which logs and re-raises
    so the runtime engages retry -> poison.
    """
    await _execute(msg, get_settings())
