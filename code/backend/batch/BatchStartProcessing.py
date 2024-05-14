import os
import logging
import json
import azure.functions as func

from utilities.helpers.embedders.integrated_vectorization_embedder import (
    IntegratedVectorizationEmbedder,
)
from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.azure_blob_storage_client import (
    AzureBlobStorageClient,
    create_queue_client,
)

bp_batch_start_processing = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


@bp_batch_start_processing.route(route="BatchStartProcessing")
def batch_start_processing(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Requested to start processing all documents received")
    env_helper: EnvHelper = EnvHelper()
    # Set up Blob Storage Client
    azure_blob_storage_client = AzureBlobStorageClient()
    # Get all files from Blob Storage
    files_data = azure_blob_storage_client.get_all_files()

    files_data = list(map(lambda x: {"filename": x["filename"]}, files_data))

    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        reprocess_integrated_vectorization(env_helper)
    else:
        # Send a message to the queue for each file
        queue_client = create_queue_client()
        for fd in files_data:
            queue_client.send_message(json.dumps(fd).encode("utf-8"))

    return func.HttpResponse(
        f"Conversion started successfully for {len(files_data)} documents.",
        status_code=200,
    )


def reprocess_integrated_vectorization(env_helper: EnvHelper):
    indexer_embedder = IntegratedVectorizationEmbedder(env_helper)
    indexer_embedder.reprocess_all()
