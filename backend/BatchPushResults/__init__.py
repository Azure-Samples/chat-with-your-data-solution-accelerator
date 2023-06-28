import logging, json
import azure.functions as func
from utilities.helper import LLMHelper

def main(msg: func.QueueMessage) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))

    # Set up LLM Helper
    llm_helper = LLMHelper()
    # Get the file name from the message
    file_name = json.loads(msg.get_body().decode('utf-8'))['filename']
    # Generate the SAS URL for the file
    file_sas = llm_helper.blob_client.get_blob_sas(file_name)

    # Check the file extension
    if file_name.endswith('.txt'):
        # Add the text to the embeddings
        llm_helper.add_embeddings_lc(file_sas)
    else:
        # Get OCR with Layout API and then add embeddigns
        llm_helper.convert_file_and_add_embeddings(file_sas , file_name)

    llm_helper.blob_client.upsert_blob_metadata(file_name, {'embeddings_added': 'true'})
