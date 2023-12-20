# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from ..common.SourceDocument import SourceDocument
from .Strategies import ChunkingSettings


class DocumentChunkingBase(ABC):
    """
    Base class for document chunking.

    This class defines the interface for document chunking operations.
    Subclasses should implement the `chunk` method to perform the actual chunking.

    Attributes:
        None

    Methods:
        chunk: Perform document chunking.

    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    def chunk(self, documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:
        """
        Chunk the given list of source documents based on the provided chunking settings.

        Args:
            documents (List[SourceDocument]): The list of source documents to be chunked.
            chunking (ChunkingSettings): The chunking settings to be applied.

        Returns:
            List[SourceDocument]: The list of chunked source documents.
        """
        pass
