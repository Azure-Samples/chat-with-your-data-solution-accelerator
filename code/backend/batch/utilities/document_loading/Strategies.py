from enum import Enum
from .Layout import LayoutDocumentLoading
from .Read import ReadDocumentLoading
from .Web import WebDocumentLoading
from .WordDocument import WordDocumentLoading


class LoadingStrategy(Enum):
    LAYOUT = "layout"
    READ = "read"
    WEB = "web"
    DOCX = "docx"


def get_document_loader(loader_strategy: str):
    if loader_strategy == LoadingStrategy.LAYOUT.value:
        return LayoutDocumentLoading()
    elif loader_strategy == LoadingStrategy.READ.value:
        return ReadDocumentLoading()
    elif loader_strategy == LoadingStrategy.WEB.value:
        return WebDocumentLoading()
    elif loader_strategy == LoadingStrategy.DOCX.value:
        return WordDocumentLoading()
    else:
        raise Exception(f"Unknown loader strategy: {loader_strategy}")
