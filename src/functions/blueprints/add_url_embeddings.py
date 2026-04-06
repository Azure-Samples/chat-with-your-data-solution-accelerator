"""Add URL embeddings: HTTP trigger to process URLs."""

import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name("AddURLEmbeddings")
@bp.route(route="AddURLEmbeddings", methods=[func.HttpMethod.POST])
async def add_url_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("AddURLEmbeddings triggered")
    # TODO: Phase 4 — parse URL, fetch content, embed, push to index
    return func.HttpResponse(
        '{"status": "not_implemented"}',
        status_code=501,
        mimetype="application/json",
    )
