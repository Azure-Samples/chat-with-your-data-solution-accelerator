"""Blob fetcher for the ``batch_push`` blueprint.

After :func:`functions.batch_push.queue_reader.parse_push_message`
hands the consumer a validated :class:`BatchPushQueueMessage`,
``batch_push`` needs the actual blob bytes to feed the parser /
chunker / embedder pipeline. This module owns only the download
call; credentials provisioning, container-client construction, and
the parse/chunk/embed/push composition are owned by the blueprint.

Why bytes (not a stream): v1 piped the blob through
``EmbedderFactory.embed_file(file_sas, file_name)`` which fetched
again via SAS URL. v2 pulls bytes once with the managed-identity
credential the blueprint already holds, then hands the buffer to
downstream parsers. Typical ingestion blobs (PDF / DOCX / TXT) are
tens of MB at most; full materialization is simpler than threading
an async iterator through every parser. Revisit only with a measured
large-blob hot path.

C5 (functions try/except sweep): SDK boundary is wrapped per the
policy in [v2/docs/exception_handling_policy.md] §"Functions
blueprints", narrow catch of ``azure.core.exceptions.AzureError``
with structured ``logger.exception`` extras, then re-raise so the
Functions runtime applies its retry / poison-queue semantics.
"""

import logging

from azure.core.exceptions import AzureError
from azure.storage.blob.aio import ContainerClient

logger = logging.getLogger(__name__)


async def download_blob(
    container_client: ContainerClient,
    filename: str,
) -> bytes:
    """Download the blob ``filename`` from ``container_client`` as bytes.

    Caller owns the lifecycle of ``container_client`` (treat it as
    DI) so this helper stays free of credentials wiring. Mirrors the
    DI contract of :func:`functions.batch_start.blob_listing.list_blobs`.

    The extra key is ``blob_filename`` (not ``filename``) to avoid
    colliding with ``logging.LogRecord``'s reserved ``filename``
    attribute, same convention as
    :func:`functions.batch_start.queue_writer.enqueue_push_message`.
    """
    try:
        downloader = await container_client.download_blob(filename)
        return await downloader.readall()
    except AzureError:
        logger.exception(
            "blob download failed",
            extra={
                "operation": "download_blob",
                "container": container_client.container_name,
                "blob_filename": filename,
            },
        )
        raise
