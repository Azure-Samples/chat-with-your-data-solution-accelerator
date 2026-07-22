"""Admin ingestion service helpers.

The helpers in this module are the per-request seams the
``POST /api/admin/documents/*`` routes call into. They resolve
collaborators from the existing provider registries (Hard Rule #4)
and delegate the actual fetch / parse / embed / push work to the
Functions-tier handlers so the two ingestion entry points (HTTP
admin route vs. HTTP Functions trigger) share one orchestration
pipeline.

Cross-package import note: the backend container's Dockerfile copies
``src`` whole, so ``functions.add_url.handler.add_url_handler`` is
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
import re
from hashlib import blake2b
from http import HTTPStatus
from urllib.parse import urlparse
from uuid import uuid4

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.paths import parser_key_for_path
from backend.core.settings import AppSettings, IngestionTrigger
from backend.models.admin import (
    IngestUrlRequest,
    IngestUrlResponse,
    ReprocessResponse,
    UploadResponse,
)
from functions.add_url.url_fetcher import fetch_url
from functions.batch_start.handler import batch_start_handler
from functions.batch_start.models import BatchStartRequest
from functions.batch_start.queue_writer import enqueue_push_message
from functions.core.contracts import BatchPushQueueMessage
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.storage_clients import storage_clients
from functions.core.storage_endpoints import resolve_storage_endpoints

logger = logging.getLogger(__name__)

# Hard upload cap surfaced to the route layer so the 413 boundary +
# the service helper agree on one number. Matches v1's admin upload
# limit; tuned alongside the Functions host's request-size ceiling.
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024

# Ext-less URLs (and any whose path extension is not a registered parser
# key) are web pages, so they're stored with the HTML parser's extension
# -- the pipeline's HtmlParser extracts clean text from them.
_DEFAULT_URL_BLOB_EXT = "html"

# Cap the derived blob stem well under the Storage 255-char blob-name
# ceiling, leaving room for the extension + a dedup suffix.
_MAX_URL_BLOB_STEM = 200

# Any run of characters outside this safe set collapses to a single
# underscore so the derived blob name carries no path separators or
# URL punctuation (it must round-trip through
# :func:`backend.services.files._validate_filename`).
_UNSAFE_BLOB_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _blob_name_for_url(url: str) -> str:
    """Derive a deterministic, flat blob filename from ``url``.

    Keeps the URL path's last-segment extension when it maps to a
    registered parser (``report.pdf`` -> ``...pdf``); otherwise stores
    the URL with the text parser's extension (:data:`_DEFAULT_URL_BLOB_EXT`).
    The stem is the sanitized ``host + path`` so distinct URLs map to
    distinct blobs and the same URL always maps to the same blob
    (re-ingesting overwrites). The result carries no path separators,
    so it round-trips through
    :func:`backend.services.files._validate_filename`.
    """
    parsed = urlparse(url)
    suffix = parser_key_for_path(parsed.path)
    extension = (
        suffix
        if suffix in ingestion_parsers_registry.registry
        else _DEFAULT_URL_BLOB_EXT
    )
    raw_stem = f"{parsed.netloc}{parsed.path}"
    if suffix:
        raw_stem = raw_stem[: -(len(suffix) + 1)]
    stem = _UNSAFE_BLOB_CHARS.sub("_", raw_stem).strip("._-")
    if stem == "":
        stem = _UNSAFE_BLOB_CHARS.sub("_", parsed.netloc).strip("._-") or "page"
    if len(stem) > _MAX_URL_BLOB_STEM:
        digest = blake2b(url.encode("utf-8"), digest_size=4).hexdigest()
        stem = f"{stem[: _MAX_URL_BLOB_STEM - 9]}-{digest}"
    return f"{stem}.{extension}"


async def ingest_url(
    request: IngestUrlRequest,
    *,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> IngestUrlResponse:
    """Download a URL, store it as a blob, and ingest it like a file.

    Fetches the URL bytes via :func:`functions.add_url.url_fetcher.fetch_url`,
    derives a deterministic blob filename (:func:`_blob_name_for_url`),
    and hands both to :func:`upload_document` -- the same path admin
    file upload uses -- so the URL's content flows through the
    identical store-then-``batch_push`` pipeline (enqueued under
    ``DIRECT_ENQUEUE``; Event-Grid-driven otherwise). This mirrors v1's
    ``download_url_and_upload_to_blob`` admin path.

    Returns the operator-facing receipt: the URL echo plus the upload
    result (derived filename, blob path, ``queued``, correlation id).
    Any ``httpx.HTTPError`` from the fetch or ``azure.core.exceptions.AzureError``
    from the blob write / enqueue propagates to the app-level handlers
    in :mod:`backend.app`, which sanitise both into 502 / 503 responses
    with no SDK detail leaked.
    """
    content = await fetch_url(request.url)
    filename = _blob_name_for_url(request.url)
    receipt = await upload_document(
        filename=filename,
        content=content,
        settings=settings,
        credential=credential,
    )
    logger.info(
        "Admin URL ingest stored.",
        extra={
            "operation": "ingest_url",
            "url": request.url,
            "blob_filename": filename,
            "ingestion_job_id": receipt.ingestion_job_id,
            "byte_count": len(content),
            "queued": receipt.queued,
        },
    )
    return IngestUrlResponse(
        url=request.url,
        filename=receipt.filename,
        blob_path=receipt.blob_path,
        ingestion_job_id=receipt.ingestion_job_id,
        queued=receipt.queued,
    )


class UploadRejected(Exception):
    """An admin upload failed a pre-ingest validation gate.

    Carries the HTTP status + detail the admin router maps onto an
    ``HTTPException`` -- keeping this service FastAPI-free (the router
    owns the HTTP translation, mirroring the ``ValueError`` -> 4xx
    mapping the other admin routes already do). ``status_code`` is an
    ``http.HTTPStatus`` (an ``int``), so it drops straight into
    ``HTTPException(status_code=...)``.
    """

    def __init__(self, *, status_code: int, detail: object) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail if isinstance(detail, str) else str(detail))


def validate_upload(filename: str, content_size: int, *, settings: AppSettings) -> None:
    """Validate one admin upload is ingestable before it is stored.

    Raises :class:`UploadRejected` (which the admin router maps to an
    ``HTTPException``) when, in order:

    * the deployment has no documents container / doc-processing queue
      configured (``503``);
    * ``filename`` is empty (``422``);
    * the extension is missing or not registered in the parser registry
      (``415`` -- the registry is the authoritative supported set,
      Hard Rule #4);
    * the resolved parser ``requires_ai_services`` but
      ``AZURE_AI_SERVICES_ENDPOINT`` is unset / not an https URL
      (``503`` -- the Document Intelligence parse step would otherwise
      poison every queued message, so the upload is refused at the
      boundary instead of reporting a success the file can never honour).
      The parser declares its own need via
      :attr:`backend.core.providers.parsers.base.BaseParser.requires_ai_services`,
      so no extension set is hard-coded here (Hard Rule #4);
    * ``content_size`` exceeds :data:`MAX_UPLOAD_SIZE_BYTES` (``413``).
    """
    if (
        not settings.storage.documents_container
        or not settings.storage.doc_processing_queue
    ):
        raise UploadRejected(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Document storage is not configured for this deployment.",
        )
    if not filename:
        raise UploadRejected(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Uploaded file must carry a non-empty filename.",
        )
    extension = parser_key_for_path(filename)
    if extension not in ingestion_parsers_registry.registry:
        supported = sorted(ingestion_parsers_registry.registry.keys())
        raise UploadRejected(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            detail={
                "msg": "Unsupported file extension.",
                "extension": extension,
                "supported": supported,
            },
        )
    parser_cls = ingestion_parsers_registry.registry.get(extension)
    if (
        parser_cls.requires_ai_services
        and not settings.foundry.services_endpoint.lower().startswith("https://")
    ):
        raise UploadRejected(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail=(
                "Document parsing is not configured for this deployment: "
                "AZURE_AI_SERVICES_ENDPOINT must be a non-empty https:// URL "
                "to parse this file type via Document Intelligence. Refusing "
                "the upload instead of reporting success for a file that "
                "cannot be indexed."
            ),
        )
    if content_size > MAX_UPLOAD_SIZE_BYTES:
        raise UploadRejected(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail={
                "msg": "Uploaded file exceeds the maximum allowed size.",
                "byte_count": content_size,
                "max_byte_count": MAX_UPLOAD_SIZE_BYTES,
            },
        )


async def upload_document(
    *,
    filename: str,
    content: bytes,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> UploadResponse:
    """Write ``content`` to the source blob container and, when the
    deploy's ingestion trigger is ``DIRECT_ENQUEUE``, enqueue an ingest
    message so ``batch_push`` picks it up.

    Two-step admin upload:

    1. Upload the bytes to the configured documents container
       (overwrite=True so re-uploading the same filename replaces
       the prior blob -- matches v1's admin upload behavior and the
       FE's per-file retry UX).
    2. Enqueue a single :class:`BatchPushQueueMessage` carrying
       ``(container_name, filename, ingestion_job_id)`` so the
       existing ``batch_push`` queue consumer runs the same
       parse / embed / push pipeline used by ``batch_start`` --
       **only** when ``settings.storage.ingestion_trigger`` is
       :attr:`IngestionTrigger.DIRECT_ENQUEUE`.

    When the trigger is :attr:`IngestionTrigger.EVENT_GRID`, a storage
    Event Grid subscription fans the ``BlobCreated`` event from step 1
    to the ``blob-events`` queue and the Functions ``blob_event``
    queue trigger translates it into the same push message -- so this
    helper writes the blob only and returns ``queued=False`` to avoid
    double-ingesting the file.

    The two steps reuse the SDK helpers already authored for the
    Functions tier (:func:`functions.core.storage_clients.storage_clients`,
    :func:`functions.batch_start.queue_writer.enqueue_push_message`)
    so a file ingested via this route lands in the same shape as one
    ingested via the bulk ``batch_start`` fan-out.

    Upload validation (extension / Document-Intelligence-config / size)
    is the caller's concern -- :func:`validate_upload` raises
    :class:`UploadRejected` and the admin route maps it to the matching
    4xx / 503. This helper trusts its inputs and reports any SDK failure
    via structured logging before re-raising per Hard Rule #14.
    """
    blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
    container_name = settings.storage.documents_container
    queue_name = settings.storage.doc_processing_queue
    ingestion_job_id = str(uuid4())
    backend_enqueues = (
        settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE
    )
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
        if backend_enqueues:
            message = BatchPushQueueMessage(
                container_name=container_name,
                filename=filename,
                ingestion_job_id=ingestion_job_id,
            )
            # ``enqueue_push_message`` already wraps its SDK boundary
            # per Hard Rule #14 -- adding another try/except here would
            # double-log on the same failure.
            await enqueue_push_message(queue_client, message)
    logger.info(
        "Admin file upload stored.",
        extra={
            "operation": "upload_document",
            "container": container_name,
            "blob_filename": filename,
            "ingestion_job_id": ingestion_job_id,
            "byte_count": len(content),
            "ingestion_trigger": settings.storage.ingestion_trigger,
            "queued": backend_enqueues,
        },
    )
    return UploadResponse(
        filename=filename,
        blob_path=f"{container_name}/{filename}",
        ingestion_job_id=ingestion_job_id,
        queued=backend_enqueues,
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
        messages = await batch_start_handler(request, container_client, queue_client)
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
