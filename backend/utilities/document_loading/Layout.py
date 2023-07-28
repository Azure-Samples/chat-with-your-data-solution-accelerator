from typing import List
from langchain.docstore.document import Document
from .DocumentLoadingBase import DocumentLoadingBase
from ..formrecognizer import AzureFormRecognizerClient

class LayoutDocumentLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()
    
    def load(self, document_url: str) -> List[Document]:
        azure_form_recognizer_client = AzureFormRecognizerClient()
        pages_content = azure_form_recognizer_client.begin_analyze_document_from_url(document_url, use_layout=True)
        documents = [Document(page_content=page['page_text'],metadata={"page_number": page['page_number'], "offset": page['offset'], "document_url": document_url}) for page in pages_content]        
        return documents       
    