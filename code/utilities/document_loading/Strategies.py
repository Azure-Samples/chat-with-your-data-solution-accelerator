from enum import Enum


class LoadingStrategy(Enum):
    """
    Represents the loading strategies for documents.
    """

    LAYOUT = 'layout'
    READ = 'read'
    WEB = 'web'
    DOCX = 'docx'


def get_document_loader(loader_strategy: str):
    """
    Returns an instance of a document loader based on the specified loader strategy.

    Args:
        loader_strategy (str): The loader strategy to use.

    Returns:
        DocumentLoader: An instance of a document loader.

    Raises:
        Exception: If an unknown loader strategy is provided.
    """
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
