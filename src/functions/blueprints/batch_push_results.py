"""Batch push results: Queue trigger to embed and push to search index."""

import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name("BatchPushResults")
@bp.queue_trigger(
    arg_name="msg",
    queue_name="doc-processing",
    connection="AzureWebJobsStorage",
)
async def batch_push_results(msg: func.QueueMessage) -> None:
    logger.info("BatchPushResults triggered for message: %s", msg.id)
    # TODO: Phase 4 — parse message, load document, embed, push to search
