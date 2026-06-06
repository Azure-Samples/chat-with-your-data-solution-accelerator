"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Queue writer for the ``batch_start`` blueprint.

``batch_start`` fans one blob -> one queue message of shape
:class:`BatchPushQueueMessage` onto the storage queue consumed by
``batch_push``. This module owns only the send call.

Hard Rule #14 (SDK boundary resilience): the SDK boundary is wrapped
per the policy in [v2/docs/exception_handling_policy.md] §"Functions
blueprints" -- narrow
catch of ``azure.core.exceptions.AzureError`` with structured
``logger.exception`` extras, then re-raise so the Functions runtime
applies its retry / poison-queue semantics.

Wire format: the message body is ``BatchPushQueueMessage.model_dump_json()``
(UTF-8 string). The Storage Queue Python SDK base64-encodes the body
by default; the envelope is well under the 64 KB encoded-message
limit so no chunking is required.
"""

import logging

from azure.core.exceptions import AzureError
from azure.storage.queue.aio import QueueClient

from functions.core.contracts import BatchPushQueueMessage

logger = logging.getLogger(__name__)


async def enqueue_push_message(
    queue_client: QueueClient,
    message: BatchPushQueueMessage,
) -> None:
    """Serialize ``message`` and send it on ``queue_client``.

    Caller owns the lifecycle of ``queue_client`` (treat it as DI) so
    this helper stays free of credentials wiring.

    Per [v2/docs/exception_handling_policy.md] §"Functions blueprints":
    catch ``AzureError`` at the SDK boundary, log with structured
    extras (operation, queue, ingestion_job_id, container,
    blob_filename), re-raise so the Functions runtime escalates per
    its retry policy. The extra key is ``blob_filename`` (not
    ``filename``) to avoid colliding with ``logging.LogRecord``'s
    reserved ``filename`` attribute, which raises ``KeyError`` at
    emit time.
    """
    body = message.model_dump_json()
    try:
        await queue_client.send_message(body)
    except AzureError:
        logger.exception(
            "queue send_message failed",
            extra={
                "operation": "send_message",
                "queue": queue_client.queue_name,
                "ingestion_job_id": message.ingestion_job_id,
                "container": message.container_name,
                "blob_filename": message.filename,
            },
        )
        raise
