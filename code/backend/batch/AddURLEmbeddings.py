import os
import logging
import traceback
import azure.functions as func
from utilities.helpers.embedders.EmbedderFactory import EmbedderFactory
from utilities.helpers.EnvHelper import EnvHelper

bp_add_url_embeddings = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


@bp_add_url_embeddings.route(route="AddURLEmbeddings")
def add_url_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    env_helper: EnvHelper = EnvHelper()
    logger.info("Python HTTP trigger function processed a request.")

    # Get Url from request
    url = req.params.get("url")
    if not url:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            url = req_body.get("url")
    # Check if url is present, compute embeddings and add them to VectorStore
    if url:
        try:
            embedder = EmbedderFactory.create(env_helper)
            embedder.embed_file(url, ".url")
        except Exception:
            return func.HttpResponse(
                f"Error: {traceback.format_exc()}", status_code=500
            )

        return func.HttpResponse(
            f"Embeddings added successfully for {url}", status_code=200
        )

    else:
        return func.HttpResponse(
            "Please pass a url on the query string or in the request body",
            status_code=400,
        )
