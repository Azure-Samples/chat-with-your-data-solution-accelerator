from typing import List
from enum import Enum
import re
from langchain.docstore.document import Document
from langchain.document_loaders import WebBaseLoader

from .formrecognizer import AzureFormRecognizerClient

class LoadingStrategy(Enum):
    LAYOUT = 'layout'
    READ = 'read'
    WEB = 'web'
    
class Loading:
    def __init__(self, loading):
        self.loading_strategy = LoadingStrategy(loading['strategy'])
        
class DocumentLoading:
    def __init__(self) -> None:
        pass
    
    def load(self, document_url: str, loading: Loading) -> List[Document]:
        if loading.loading_strategy == LoadingStrategy.LAYOUT:
            return self.layout_load(document_url)
        elif loading.loading_strategy == LoadingStrategy.READ:
            return self.read_load(document_url)
        elif loading.loading_strategy == LoadingStrategy.WEB:
            return self.web_load(document_url)
        else:
            raise Exception(f"Unknown loading strategy: {loading.loading_strategy}")
        
    def layout_load(self, document_url: str) -> List[Document]:
        azure_form_recognizer_client = AzureFormRecognizerClient()
        pages_content = azure_form_recognizer_client.begin_analyze_document_from_url(document_url, use_layout=True)
        documents = [Document(page_content=page['page_text'],metadata={"page_number": page['page_number'], "offset": page['offset'], "document_url": document_url}) for page in pages_content]        
        return documents            
        
    def read_load(self, document_url: str) -> List[Document]:
        azure_form_recognizer_client = AzureFormRecognizerClient()
        pages_content = azure_form_recognizer_client.begin_analyze_document_from_url(document_url, use_layout=True)
        documents = [Document(page_content=page['page_text'],metadata={"page_number": page['page_number'], 'offset': page['offset'], "document_url": document_url}) for page in pages_content]        
        return documents
                
    def web_load(self, document_url: str) -> List[Document]:
        documents = WebBaseLoader(document_url).load() 
        for document in documents:
            document.page_content = re.sub('\n{3,}', '\n\n', document.page_content)
            # Remove half non-ascii character from start/end of doc content
            pattern = re.compile(
                r"[\x00-\x1f\x7f\u0080-\u00a0\u2000-\u3000\ufff0-\uffff]"
            )
            document.page_content = re.sub(pattern, "", document.page_content)
            if document.page_content == "":
                documents.remove(document)
            document.metadata['document_url'] = document.metadata['source']
        return documents