"""Document download service.

Pillar: Stable Core
Phase: 7 (Testing + Documentation)

Reads a single ingested document blob back out of the documents
container so the chat UI can deep-link a citation to its source file.

The blob name is the same value the ingestion pipeline wrote into the
search index ``title`` field (``chunk.source`` -> ``SearchDocument.title``),
so a citation's ``title`` round-trips straight back to ``download_blob``
without any path reconstruction.

A read-only ``ContainerClient`` is constructed directly here (rather than
through :func:`functions.core.storage_clients.storage_clients`, which also
builds a ``QueueClient``) so document serving stays independent of the
ingestion-queue configuration -- reading a document does not require a
push queue.

Error contract (mapped to HTTP by the router layer):

* :class:`ValueError` -- the filename is empty, overlong, or carries a
  path-traversal / control-character payload. Rejected before any SDK
  call. The missing-file and traversal cases are *expected* inputs, so
  neither is logged at error level.
* :class:`FileNotFoundError` -- no blob with that name exists.
* :class:`azure.core.exceptions.AzureError` -- any other storage
  failure, logged with structured extras then re-raised per Hard Rule
  #14 so the app-level handlers can sanitise it.
"""

import logging

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob.aio import ContainerClient

from backend.core.settings import AppSettings
from functions.core.storage_endpoints import resolve_storage_endpoints

logger = logging.getLogger(__name__)

_MAX_FILENAME_LENGTH = 255


def _validate_filename(filename: str) -> None:
    """Reject blob names that could traverse the container or are malformed.

    The documents container stores flat blob names (the original upload
    filename), so a legitimate request never carries a path separator or
    a parent-directory segment. Rejecting them keeps the download key
    confined to a single blob in a single container.
    """
    if not filename:
        raise ValueError("filename must not be empty.")
    if len(filename) > _MAX_FILENAME_LENGTH:
        raise ValueError("filename exceeds the maximum allowed length.")
    if "/" in filename or "\\" in filename:
        raise ValueError("filename must not contain path separators.")
    if ".." in filename:
        raise ValueError("filename must not contain parent-directory segments.")
    if any(ord(character) < 0x20 for character in filename):
        raise ValueError("filename must not contain control characters.")


async def download_document(
    filename: str,
    *,
    settings: AppSettings,
    credential: AsyncTokenCredential,
) -> bytes:
    """Download the document blob ``filename`` from the documents container.

    Returns the raw blob bytes. The caller (router layer) owns
    content-type negotiation and HTTP status mapping; this helper is
    concerned only with validation and the storage read.
    """
    _validate_filename(filename)
    blob_endpoint, _ = resolve_storage_endpoints(settings.storage)
    container_name = settings.storage.documents_container
    async with ContainerClient(
        account_url=blob_endpoint,
        container_name=container_name,
        credential=credential,
    ) as container_client:
        try:
            downloader = await container_client.download_blob(filename)
            return await downloader.readall()
        except ResourceNotFoundError as exc:
            # Missing blob is an expected 404, not a server error -- do
            # not log at error level; let the router translate it.
            raise FileNotFoundError(filename) from exc
        except AzureError:
            logger.exception(
                "document download failed",
                extra={
                    "operation": "download_document",
                    "container": container_name,
                    "blob_filename": filename,
                },
            )
            raise
