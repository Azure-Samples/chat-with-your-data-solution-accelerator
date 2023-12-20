# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from ..common.SourceDocument import SourceDocument


class DocumentLoadingBase(ABC):
    """
    Base class for document loading.

    This class defines the interface for loading documents from a given URL.
    Subclasses must implement the `load` method.

    Attributes:
        None

    Methods:
        load: Load documents from a given URL.

    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    def load(self, document_url: str) -> List[SourceDocument]:
        """
        Loads a document from the specified URL.

        Args:
            document_url (str): The URL of the document to load.

        Returns:
            List[SourceDocument]: A list of SourceDocument objects representing the loaded document.
        """
        pass
