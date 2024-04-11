import logging
import json
import azure.functions as func
from urllib.parse import urlparse
import sys

from utilities.helpers.EnvHelper import EnvHelper
from utilities.helpers.AzureBlobStorageHelper import AzureBlobStorageClient
from utilities.helpers.DocumentProcessorHelper import DocumentProcessor
from utilities.helpers.ConfigHelper import ConfigHelper

sys.path.append("..")

bp_batch_push_results = func.Blueprint()
env_helper: EnvHelper = EnvHelper()

logger = logging.getLogger(__name__)
logger.setLevel(env_helper.LOGLEVEL)


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
    logger.info(
        "Python queue trigger function processed a queue item: %s",
        msg.get_body().decode("utf-8"),
    )
    document_processor = DocumentProcessor()
    blob_client = AzureBlobStorageClient()
    # Get the file name from the message
    file_name = _get_file_name_from_message(msg)
    # Generate the SAS URL for the file
    file_sas = blob_client.get_blob_sas(file_name)
    # Get file extension's processors
    file_extension = file_name.split(".")[-1]
    processors = list(
        filter(
            lambda x: x.document_type.lower() == file_extension.lower(),
            ConfigHelper.get_active_config_or_default().document_processors,
        )
    )
    # Process the file
    document_processor.process(source_url=file_sas, processors=processors)
    blob_client.upsert_blob_metadata(file_name, {"embeddings_added": "true"})
