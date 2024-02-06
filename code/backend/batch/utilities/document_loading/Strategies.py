from enum import Enum


class LoadingStrategy(Enum):
    LAYOUT = "layout"
    READ = "read"
    WEB = "web"
    DOCX = "docx"


def get_document_loader(loader_strategy: str):
    if loader_strategy == LoadingStrategy.LAYOUT.value:
        from .Layout import LayoutDocumentLoading

        return LayoutDocumentLoading()
    elif loader_strategy == LoadingStrategy.READ.value:
        from .Read import ReadDocumentLoading

        return ReadDocumentLoading()
    elif loader_strategy == LoadingStrategy.WEB.value:
        from .Web import WebDocumentLoading

        return WebDocumentLoading()
    elif loader_strategy == LoadingStrategy.DOCX.value:
        from .WordDocument import WordDocumentLoading

        return WordDocumentLoading()
    else:
        raise Exception(f"Unknown loader strategy: {loader_strategy}")
