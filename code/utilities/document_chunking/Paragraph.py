from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument


class ParagraphDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    # TO DO: Implement the following chunking strategies
    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        raise NotImplementedError("Paragraph chunking is not implemented yet")
