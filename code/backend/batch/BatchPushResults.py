import os
import logging
import json
import azure.functions as func
from urllib.parse import urlparse

from utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient
from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.embedders.embedder_factory import EmbedderFactory

bp_batch_push_results = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


def _get_file_name_from_message(msg: func.QueueMessage) -> str:
    message_body = json.loads(msg.get_body().decode("utf-8"))
    return message_body.get(
        "filename",
        "/".join(
            urlparse(message_body.get("data", {}).get("url", "")).path.split("/")[2:]
        ),
    )


@bp_batch_push_results.queue_trigger(
    arg_name="msg", queue_name="doc-processing", connection="AzureWebJobsStorage"
)
def batch_push_results(msg: func.QueueMessage) -> None:
    do_batch_push_results(msg)


def do_batch_push_results(msg: func.QueueMessage) -> None:
    env_helper: EnvHelper = EnvHelper()
    logger.info(
        "Python queue trigger function processed a queue item: %s",
        msg.get_body().decode("utf-8"),
    )

    blob_client = AzureBlobStorageClient()
    # Get the file name from the message
    file_name = _get_file_name_from_message(msg)
    # Generate the SAS URL for the file
    file_sas = blob_client.get_blob_sas(file_name)
    # Process the file
    embedder = EmbedderFactory.create(env_helper)
    embedder.embed_file(file_sas, file_name)
