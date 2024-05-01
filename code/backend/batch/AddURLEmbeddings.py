import io
import os
import logging
import traceback
import azure.functions as func
import requests
from bs4 import BeautifulSoup

from utilities.helpers.EnvHelper import EnvHelper
from utilities.helpers.AzureBlobStorageClient import AzureBlobStorageClient
from utilities.helpers.DocumentProcessorHelper import DocumentProcessor
from utilities.helpers.ConfigHelper import ConfigHelper


bp_add_url_embeddings = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


@bp_add_url_embeddings.route(route="AddURLEmbeddings")
def add_url_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Python HTTP trigger function processed a request.")

    # Get Url from request
    url = None
    try:
        req_body = req.get_json()
    except ValueError:
        pass
    else:
        url = req_body.get("url")

    if not url:
        return func.HttpResponse(
            "Please pass a url on the query string or in the request body",
            status_code=400,
        )

    env_helper: EnvHelper = EnvHelper()
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        return download_url_and_upload_to_blob(url)
    else:
        return process_url_contents_directly(url)


def process_url_contents_directly(url: str):
    try:
        config = ConfigHelper.get_active_config_or_default()
        document_processor = DocumentProcessor()
        processors = list(
            filter(lambda x: x.document_type == "url", config.document_processors)
        )
        document_processor.process(source_url=url, processors=processors)
    except Exception:
        return func.HttpResponse(f"Error: {traceback.format_exc()}", status_code=500)

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
        return func.HttpResponse(f"Url {url} added to knowledge base", status_code=200)

    except Exception:
        return func.HttpResponse(
            f"Error: {traceback.format_exc()}. Exception occurred while adding {url} to the knowledge base.",
            status_code=500,
        )
