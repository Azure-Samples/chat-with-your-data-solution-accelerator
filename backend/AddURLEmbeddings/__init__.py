import logging, traceback

import azure.functions as func
from utilities.DocumentProcessor import DocumentProcessor

def main(req: func.HttpRequest) -> func.HttpResponse:
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
            document_processor = DocumentProcessor()       
            document_processor.process(url, '.url')
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
