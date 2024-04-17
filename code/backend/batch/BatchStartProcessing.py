import logging
import json
import azure.functions as func
import sys
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy
from utilities.helpers.EnvHelper import EnvHelper
from utilities.helpers.AzureBlobStorageHelper import AzureBlobStorageClient

sys.path.append("..")
bp_batch_start_processing = func.Blueprint()
env_helper: EnvHelper = EnvHelper()


@bp_batch_start_processing.route(route="BatchStartProcessing")
def batch_start_processing(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Requested to start processing all documents received")
    # Set up Blob Storage Client
    azure_blob_storage_client = AzureBlobStorageClient()
    # Get all files from Blob Storage
    files_data = azure_blob_storage_client.get_all_files()
    # Filter out files that have already been processed
    files_data = (
        list(filter(lambda x: not x["embeddings_added"], files_data))
        if req.params.get("process_all") != "true"
        else files_data
    )
    files_data = list(map(lambda x: {"filename": x["filename"]}, files_data))
    # Create the QueueClient object
    queue_client = QueueClient.from_connection_string(
        azure_blob_storage_client.connect_str,
        env_helper.DOCUMENT_PROCESSING_QUEUE_NAME,
        message_encode_policy=BinaryBase64EncodePolicy(),
    )
    # Send a message to the queue for each file
    for fd in files_data:
        queue_client.send_message(json.dumps(fd).encode("utf-8"))

    return func.HttpResponse(
        f"Conversion started successfully for {len(files_data)} documents.",
        status_code=200,
    )
