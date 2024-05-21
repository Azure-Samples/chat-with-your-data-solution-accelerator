from typing import List
from .document_chunking_base import DocumentChunkingBase
from .chunking_strategy import ChunkingSettings
from ..common.source_document import SourceDocument


class ParagraphDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    # TO DO: Implement the following chunking strategies
    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        raise NotImplementedError("Paragraph chunking is not implemented yet")
