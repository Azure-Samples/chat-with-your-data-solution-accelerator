from typing import List
from urllib.parse import urlparse
from langchain.docstore.document import Document
from ..document_chunking import get_document_chunker, ChunkingSettings, ChunkingStrategy


class DocumentChunking:
    """
    Helper class for chunking documents based on a given chunking strategy.
    """

    def __init__(self) -> None:
        pass

    def chunk(self, documents: List[Document], chunking: ChunkingSettings) -> List[Document]:
        """
        Chunk the given list of documents based on the specified chunking strategy.

        Args:
            documents (List[Document]): The list of documents to be chunked.
            chunking (ChunkingSettings): The chunking settings specifying the chunking strategy.

        Returns:
            List[Document]: The list of chunked documents.
        """
        chunker = get_document_chunker(chunking.chunking_strategy.value)
        if chunker is None:
            raise Exception(
                f"Unknown chunking strategy: {chunking.chunking_strategy.value}")
        return chunker.chunk(documents, chunking)
