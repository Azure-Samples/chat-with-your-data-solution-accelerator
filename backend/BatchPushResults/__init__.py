import logging, json
import azure.functions as func
from utilities.azureblobstorage import AzureBlobStorageClient
from utilities.DocumentProcessor import DocumentProcessor
from utilities.DocumentLoading import Loading, LoadingStrategy

def main(msg: func.QueueMessage) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))

    document_processor = DocumentProcessor()
    blob_client = AzureBlobStorageClient()
    # Get the file name from the message
    file_name = json.loads(msg.get_body().decode('utf-8'))['filename']
    # Generate the SAS URL for the file
    file_sas = blob_client.get_blob_sas(file_name)

    # Check the file extension
    if file_name.endswith('.txt'):
        # Add the text to the embeddings
        document_processor.process(file_sas, loading=Loading({"strategy": "web"}))
    else:
        # Get OCR with Layout API and then add embeddigns
        document_processor.process(file_sas, loading=Loading({"strategy": "layout"}))

    blob_client.upsert_blob_metadata(file_name, {'embeddings_added': 'true'})
