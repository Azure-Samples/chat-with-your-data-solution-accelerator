import io
import os
import logging
import traceback
import azure.functions as func
import requests
from bs4 import BeautifulSoup
from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient
from utilities.helpers.embedders.embedder_factory import EmbedderFactory

bp_add_url_embeddings = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


@bp_add_url_embeddings.route(route="AddURLEmbeddings")
def add_url_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    env_helper: EnvHelper = EnvHelper()
    logger.info("Python HTTP trigger function processed a request.")

    # Get Url from request
    url = None
    try:
        url = req.get_json().get("url")
    except Exception:
        url = None

    if not url:
        return func.HttpResponse(
            "Please pass a URL on the query string or in the request body",
            status_code=400,
        )

    env_helper: EnvHelper = EnvHelper()
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        return download_url_and_upload_to_blob(url)
    else:
        return process_url_contents_directly(url, env_helper)


def process_url_contents_directly(url: str, env_helper: EnvHelper):
    try:
        embedder = EmbedderFactory.create(env_helper)
        embedder.embed_file(url, ".url")
    except Exception:
        logger.error(
            f"Error while processing contents of URL {url}: {traceback.format_exc()}"
        )
        return func.HttpResponse(
            f"Unexpected error occurred while processing the contents of the URL {url}",
            status_code=500,
        )

    return func.HttpResponse(
        f"Embeddings added successfully for {url}", status_code=200
    )


def download_url_and_upload_to_blob(url: str):
    try:
        response = requests.get(url)
        parsed_data = BeautifulSoup(response.content, "html.parser")
        with io.BytesIO(parsed_data.get_text().encode("utf-8")) as stream:
            blob_client = AzureBlobStorageClient()
            blob_client.upload_file(stream, url, metadata={"title": url})
        return func.HttpResponse(f"URL {url} added to knowledge base", status_code=200)

    except Exception:
        logger.error(
            f"Error while adding URL {url} to the knowledge base: {traceback.format_exc()}"
        )
        return func.HttpResponse(
            f"Error occurred while adding {url} to the knowledge base.",
            status_code=500,
        )
