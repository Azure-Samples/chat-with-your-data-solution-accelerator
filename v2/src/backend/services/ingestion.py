"""Admin ingestion service helpers.

Pillar: Stable Core
Phase: 7 (Testing + Documentation -- admin-side ingestion surface so the
FE can drive URL ingest / file upload / reprocess-all through FastAPI
instead of reaching into the Functions host)

The helpers in this module are the per-request seams the
``POST /api/admin/documents/*`` routes call into. They resolve
collaborators from the existing provider registries (Hard Rule #4)
and delegate the actual fetch / parse / embed / push work to the
Functions-tier handlers so the two ingestion entry points (HTTP
admin route vs. HTTP Functions trigger) share one orchestration
pipeline.

Cross-package import note: the backend container's Dockerfile copies
``v2/src`` whole, so ``functions.add_url.handler.add_url_handler`` is
importable here at runtime. That import is deliberate -- the
add-URL orchestration (fetch -> parse -> embed -> push) is identical
across both entry points; duplicating it would force the two paths
to drift.

Per-request resource ownership: the lifespan-cached credential +
search provider on ``app.state`` are reused (no fresh
``DefaultAzureCredential`` per request); the embedder is built per
request and closed in a ``finally`` block since its async client
state is request-scoped, mirroring the discipline in
:mod:`functions.add_url.blueprint`.
"""

import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse
from uuid import uuid4

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings
from backend.models.admin import (
    IngestUrlRequest,
    IngestUrlResponse,
    ReprocessResponse,
    UploadResponse,
)
from functions.add_url.handler import AddUrlRequest, add_url_handler
from functions.batch_start.handler import batch_start_handler
from functions.batch_start.models import BatchStartRequest
from functions.batch_start.queue_writer import enqueue_push_message
from functions.core.contracts import BatchPushQueueMessage
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.storage_clients import storage_clients
from functions.core.storage_endpoints import resolve_storage_endpoints

logger = logging.getLogger(__name__)

# Ext-less URLs (``https://example.com/article``) fall back to the
# text parser. Mirrors :data:`functions.add_url.blueprint._DEFAULT_PARSER_KEY`
# -- duplicated rather than imported because the constant is a local
# default policy for each ingestion entry point.
_DEFAULT_PARSER_KEY = "txt"

# Hardcoded embedder key. Mirrors the same choice in
# :func:`functions.add_url.blueprint._execute`. Promotes to a settings
# field when a second concrete embedder lands.
_DEFAULT_EMBEDDER_KEY = "azure_openai"

# Hard upload cap surfaced to the route layer so the 413 boundary +
# the service helper agree on one number. Matches v1's admin upload
# limit; tuned alongside the Functions host's request-size ceiling.
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


def _parser_key_for_url(url: str) -> str:
    """Return the parser-registry key for ``url``.

    Extracts the URL path's lowercase extension (sans dot). Falls
    back to :data:`_DEFAULT_PARSER_KEY` when the path has no
    extension so ext-less URLs still route to a parser. Mirrors
    :func:`functions.add_url.blueprint._parser_key_for_url` -- per
    Stable Core per-blueprint independence, this is duplicated, not
    imported.
    """
    parsed = urlparse(url)
    suffix = PurePosixPath(parsed.path).suffix.lstrip(".").lower()
    return suffix or _DEFAULT_PARSER_KEY


async def ingest_url(
    request: IngestUrlRequest,
    *,
    settings: AppSettings,
    credential: AsyncTokenCredential,
    search_provider: BaseSearch,
) -> IngestUrlResponse:
    """Fetch a URL, parse + embed + index its chunks, return job receipt.

    Resolves the parser registry entry for the URL's path extension
    and the configured embedder, then delegates to
    :func:`functions.add_url.handler.add_url_handler` -- the same
    orchestration the Functions HTTP trigger uses, so an URL ingested
    via this route lands in the same shape as one ingested via the
    queue path.

    Returns the operator-facing response carrying the correlation id
    + the count of chunks pushed to the search index. Any
    ``httpx.HTTPError`` from the fetch or upstream
    ``azure.core.exceptions.AzureError`` from the embedder / search
    write propagates to the app-level handlers in :mod:`backend.app`
    which sanitise both into 502 / 503 responses with no SDK detail
    leaked.
    """
    parser_cls = ingestion_parsers_registry.registry.get(
        _parser_key_for_url(request.url)
    )
    parser = parser_cls(settings=settings, credential=credential)
    embedder_cls = embedders_registry.registry.get(_DEFAULT_EMBEDDER_KEY)
    embedder = embedder_cls(settings=settings, credential=credential)
    try:
        documents = await add_url_handler(
            AddUrlRequest(url=request.url, ingestion_job_id=request.ingestion_job_id),
            parser,
            embedder,
            search_provider,
        )
    finally:
        await embedder.aclose()
    logger.info(
        "Admin URL ingest succeeded.",
        extra={
            "operation": "ingest_url",
            "url": request.url,
            "ingestion_job_id": request.ingestion_job_id,
            "document_count": len(documents),
        },
    )
    return IngestUrlResponse(
        ingestion_job_id=request.ingestion_job_id,
        url=request.url,
        document_count=len(documents),
    )


async def upload_document(
    *,
    filename: str,
    content: bytes,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> UploadResponse:
    """Write ``content`` to the source blob container and enqueue an
    ingest message so ``batch_push`` will pick it up.

    Two-step admin upload:

    1. Upload the bytes to the configured documents container
       (overwrite=True so re-uploading the same filename replaces
       the prior blob -- matches v1's admin upload behavior and the
       FE's per-file retry UX).
    2. Enqueue a single :class:`BatchPushQueueMessage` carrying
       ``(container_name, filename, ingestion_job_id)`` so the
       existing ``batch_push`` queue consumer runs the same
       parse / embed / push pipeline used by ``batch_start``.

    The two steps reuse the SDK helpers already authored for the
    Functions tier (:func:`functions.core.storage_clients.storage_clients`,
    :func:`functions.batch_start.queue_writer.enqueue_push_message`)
    so a file ingested via this route lands in the same shape as one
    ingested via the bulk ``batch_start`` fan-out.

    Filename extension validation is the caller's concern (the route
    layer maps unknown extensions to ``415 Unsupported Media Type``
    using the parser registry). Size validation is also caller-side
    (the route caps reads at :data:`MAX_UPLOAD_SIZE_BYTES` and
    returns 413). The helper trusts its inputs and reports any SDK
    failure via structured logging before re-raising per Hard Rule
    #14.
    """
    blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
    container_name = settings.storage.documents_container
    queue_name = settings.storage.doc_processing_queue
    ingestion_job_id = str(uuid4())
    async with storage_clients(
        credential=credential,
        blob_endpoint=blob_endpoint,
        queue_endpoint=queue_endpoint,
        container_name=container_name,
        queue_name=queue_name,
    ) as (container_client, queue_client):
        try:
            await container_client.upload_blob(
                name=filename, data=content, overwrite=True
            )
        except AzureError:
            logger.exception(
                "blob upload_blob failed",
                extra={
                    "operation": "upload_blob",
                    "container": container_name,
                    "blob_filename": filename,
                    "ingestion_job_id": ingestion_job_id,
                },
            )
            raise
        message = BatchPushQueueMessage(
            container_name=container_name,
            filename=filename,
            ingestion_job_id=ingestion_job_id,
        )
        # ``enqueue_push_message`` already wraps its SDK boundary per
        # Hard Rule #14 -- adding another try/except here would
        # double-log on the same failure.
        await enqueue_push_message(queue_client, message)
    logger.info(
        "Admin file upload queued for indexing.",
        extra={
            "operation": "upload_document",
            "container": container_name,
            "blob_filename": filename,
            "ingestion_job_id": ingestion_job_id,
            "byte_count": len(content),
        },
    )
    return UploadResponse(
        filename=filename,
        blob_path=f"{container_name}/{filename}",
        ingestion_job_id=ingestion_job_id,
        queued=True,
    )


async def reprocess_all(
    *,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> ReprocessResponse:
    """Fan every blob in the documents container out to the push queue.

    Delegates to :func:`functions.batch_start.handler.batch_start_handler`
    -- the same orchestration used by the Functions ``POST /api/batch_start``
    HTTP trigger -- so a reprocess driven from the admin UI lands in
    the same shape as one driven from the Functions tier. The two
    entry points share one orchestration pipeline; duplicating the
    fan-out logic here would force the two paths to drift.

    The handler already wraps its SDK boundaries (listing blobs,
    enqueueing envelopes) and returns the list of envelopes it wrote
    so this layer only has to translate the result into a typed
    receipt. An empty container yields ``ingestion_job_id=None`` so
    the FE can distinguish "nothing to do" from "queued N items".

    Caller-side preconditions: the route layer is responsible for
    surfacing the 503 when ``documents_container`` /
    ``doc_processing_queue`` are unconfigured; this helper trusts
    its inputs.
    """
    blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
    container_name = settings.storage.documents_container
    queue_name = settings.storage.doc_processing_queue
    request = BatchStartRequest(container_name=container_name)
    async with storage_clients(
        credential=credential,
        blob_endpoint=blob_endpoint,
        queue_endpoint=queue_endpoint,
        container_name=container_name,
        queue_name=queue_name,
    ) as (container_client, queue_client):
        messages = await batch_start_handler(
            request, container_client, queue_client
        )
    ingestion_job_id = messages[0].ingestion_job_id if messages else None
    logger.info(
        "Admin reprocess-all fan-out queued.",
        extra={
            "operation": "reprocess_all",
            "container": container_name,
            "ingestion_job_id": ingestion_job_id,
            "enqueued_count": len(messages),
        },
    )
    return ReprocessResponse(
        ingestion_job_id=ingestion_job_id,
        enqueued_count=len(messages),
    )


__all__ = [
    "MAX_UPLOAD_SIZE_BYTES",
    "ingest_url",
    "reprocess_all",
    "upload_document",
]
