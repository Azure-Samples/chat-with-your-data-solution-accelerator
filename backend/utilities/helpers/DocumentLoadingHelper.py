from typing import List
from langchain.docstore.document import Document
from ..document_loading import get_document_loader, LoadingSettings, LoadingStrategy
       
class DocumentLoading:
    def __init__(self) -> None:
        pass
    
    def load(self, document_url: str, loading: LoadingSettings) -> List[Document]:
        loader = get_document_loader(loading.loading_strategy.value)
        if loader is None:
            raise Exception(f"Unknown loader strategy: {loading.loading_strategy.value}")
        return loader.load(document_url)
