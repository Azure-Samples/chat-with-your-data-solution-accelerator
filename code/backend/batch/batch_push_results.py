import os
import logging
import json
from urllib.parse import urlparse
import azure.functions as func

from utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient
from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.embedders.embedder_factory import EmbedderFactory
from utilities.search.search import Search

bp_batch_push_results = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


def _get_file_name_from_message(message_body) -> str:
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
    message_body = json.loads(msg.get_body().decode("utf-8"))
    logger.info("Process Document Event queue function triggered: %s", message_body)

    event_type = message_body.get("eventType", "")
    # We handle "" in this scenario for backwards compatibility
    # This function is primarily triggered by an Event Grid queue message from the blob storage
    # However, it can also be triggered using a legacy schema from BatchStartProcessing
    if event_type in ("", "Microsoft.Storage.BlobCreated"):
        logger.info("Handling 'Blob Created' event with message body: %s", message_body)
        _process_document_created_event(message_body)

    elif event_type == "Microsoft.Storage.BlobDeleted":
        logger.info("Handling 'Blob Deleted' event with message body: %s", message_body)
        _process_document_deleted_event(message_body)

    else:
        logger.exception("Received an unrecognized event type: %s", event_type)
        raise NotImplementedError(f"Unknown event type received: {event_type}")


def _process_document_created_event(message_body) -> None:
    env_helper: EnvHelper = EnvHelper()

    blob_client = AzureBlobStorageClient()
    file_name = _get_file_name_from_message(message_body)
    file_sas = blob_client.get_blob_sas(file_name)

    embedder = EmbedderFactory.create(env_helper)
    embedder.embed_file(file_sas, file_name)


def _process_document_deleted_event(message_body) -> None:
    env_helper: EnvHelper = EnvHelper()
    search_handler = Search.get_search_handler(env_helper)

    blob_url = message_body.get("data", {}).get("url", "")
    search_handler.delete_from_index(blob_url)
