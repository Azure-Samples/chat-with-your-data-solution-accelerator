"""Batch start: HTTP trigger to queue all documents for processing."""

import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name("BatchStartProcessing")
@bp.route(route="BatchStartProcessing", methods=[func.HttpMethod.POST])
async def batch_start(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("BatchStartProcessing triggered")
    # TODO: Phase 4 — list blobs, queue messages for each
    return func.HttpResponse(
        '{"status": "not_implemented"}',
        status_code=501,
        mimetype="application/json",
    )
