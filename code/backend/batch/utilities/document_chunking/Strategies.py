from enum import Enum


class ChunkingStrategy(Enum):
    LAYOUT = "layout"
    PAGE = "page"
    FIXED_SIZE_OVERLAP = "fixed_size_overlap"
    PARAGRAPH = "paragraph"


def get_document_chunker(chunking_strategy: str):
    if chunking_strategy == ChunkingStrategy.LAYOUT.value:
        from .Layout import LayoutDocumentChunking

        return LayoutDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PAGE.value:
        from .Page import PageDocumentChunking

        return PageDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.FIXED_SIZE_OVERLAP.value:
        from .FixedSizeOverlap import FixedSizeOverlapDocumentChunking

        return FixedSizeOverlapDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PARAGRAPH.value:
        from .Paragraph import ParagraphDocumentChunking

        return ParagraphDocumentChunking()
    else:
        raise Exception(f"Unknown chunking strategy: {chunking_strategy}")


class ChunkingSettings:
    def __init__(self, chunking: dict):
        self.chunking_strategy = ChunkingStrategy(chunking["strategy"])
        self.chunk_size = chunking["size"]
        self.chunk_overlap = chunking["overlap"]

    def __eq__(self, other: object) -> bool:
        if isinstance(self, other.__class__):
            return (
                self.chunking_strategy == other.chunking_strategy
                and self.chunk_size == other.chunk_size
                and self.chunk_overlap == other.chunk_overlap
            )
        else:
            return False
