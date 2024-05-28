from typing import List

from ..common.source_document import SourceDocument
from ..document_chunking.chunking_strategy import ChunkingSettings, ChunkingStrategy
from ..document_chunking.strategies import get_document_chunker

__all__ = ["ChunkingStrategy"]


class DocumentChunking:
    def __init__(self) -> None:
        pass

    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        chunker = get_document_chunker(chunking.chunking_strategy.value)
        if chunker is None:
            raise Exception(
                f"Unknown chunking strategy: {chunking.chunking_strategy.value}"
            )
        return chunker.chunk(documents, chunking)
