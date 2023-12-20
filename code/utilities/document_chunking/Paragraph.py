from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument


class ParagraphDocumentChunking(DocumentChunkingBase):
    """
    A class that implements the paragraph chunking strategy for document chunking.
    """

    def __init__(self) -> None:
        super().__init__()

    def chunk(self, documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:
        """
        Chunk the given documents using paragraph chunking strategy.

        Args:
            documents (List[SourceDocument]): The list of source documents to be chunked.
            chunking (ChunkingSettings): The chunking settings to be applied.

        Returns:
            List[SourceDocument]: The list of chunked source documents.
        """
        raise NotImplementedError("Paragraph chunking is not implemented yet")
