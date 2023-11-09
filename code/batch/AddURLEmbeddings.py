import logging, traceback
import azure.functions as func
import sys
sys.path.append("..")
from utilities.helpers.DocumentProcessorHelper import DocumentProcessor
from utilities.helpers.ConfigHelper import ConfigHelper

bp_add_url_embeddings = func.Blueprint() 

@bp_add_url_embeddings.route(route="AddURLEmbeddings")
def add_url_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    # Get Url from request
    url = req.params.get('url')
    if not url:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            url = req_body.get('url')
    # Check if url is present, compute embeddings and add them to VectorStore     
    if url:
        try:
            config = ConfigHelper.get_active_config_or_default()
            document_processor = DocumentProcessor()
            processors = list(filter(lambda x : x.document_type == "url" , config.document_processors))
            document_processor.process(source_url=url, processors=processors)
        except Exception as e:
            return func.HttpResponse(
                f"Error: {traceback.format_exc()}",
                status_code=500)
        
        return func.HttpResponse(
            f"Embeddings added successfully for {url}",
            status_code=200)
        
    else:
        return func.HttpResponse(
            "Please pass a url on the query string or in the request body",
            status_code=400)
