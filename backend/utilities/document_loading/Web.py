from typing import List
import re
from .DocumentLoadingBase import DocumentLoadingBase
from langchain.docstore.document import Document
from langchain.document_loaders import WebBaseLoader

class WebDocumentLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()
    
    def load(self, document_url: str) -> List[Document]:
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
