from typing import List
from langchain.docstore.document import Document
from ..document_loading import get_document_loader, LoadingSettings, LoadingStrategy


class DocumentLoading:
    """
    Helper class for loading documents from a specified URL using loading settings.
    """

    def __init__(self) -> None:
        pass

    def load(self, document_url: str, loading: LoadingSettings) -> List[Document]:
        """
        Load a document from the specified URL using the given loading settings.

        Args:
            document_url (str): The URL of the document to load.
            loading (LoadingSettings): The loading settings to use.

        Returns:
            List[Document]: A list of loaded documents.
        """
        loader = get_document_loader(loading.loading_strategy.value)
        if loader is None:
            raise Exception(
                f"Unknown loader strategy: {loading.loading_strategy.value}")
        return loader.load(document_url)
