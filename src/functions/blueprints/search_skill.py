"""Search skill: Anonymous HTTP trigger for Cognitive Search custom skill."""

import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name("SearchSkill")
@bp.route(route="SearchSkill", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
async def search_skill(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("SearchSkill triggered")
    # TODO: Phase 4 — combine pages and chunk numbers
    return func.HttpResponse(
        '{"values": []}',
        status_code=200,
        mimetype="application/json",
    )
