"""Conversation function: HTTP trigger for async conversation handling."""

import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name("Conversation")
@bp.route(route="Conversation", methods=[func.HttpMethod.POST])
async def conversation(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Conversation function triggered")
    # TODO: Phase 4 — async conversation handler
    return func.HttpResponse(
        '{"status": "not_implemented"}',
        status_code=501,
        mimetype="application/json",
    )
