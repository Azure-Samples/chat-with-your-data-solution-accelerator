import logging, json
import azure.functions as func
from utilities.azureblobstorage import AzureBlobStorageClient
from utilities.DocumentProcessor import DocumentProcessor

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
        document_processor.process_url_and_store_in_vector_store(file_sas)
    else:
        # Get OCR with Layout API and then add embeddigns
        document_processor.convert_file_create_embedings_and_store(file_sas , file_name)

    blob_client.upsert_blob_metadata(file_name, {'embeddings_added': 'true'})
