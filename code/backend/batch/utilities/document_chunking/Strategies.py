from .ChunkingStrategy import ChunkingStrategy
from .Layout import LayoutDocumentChunking
from .Page import PageDocumentChunking
from .FixedSizeOverlap import FixedSizeOverlapDocumentChunking
from .Paragraph import ParagraphDocumentChunking


def get_document_chunker(chunking_strategy: str):
    if chunking_strategy == ChunkingStrategy.LAYOUT.value:
        return LayoutDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PAGE.value:
        return PageDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.FIXED_SIZE_OVERLAP.value:
        return FixedSizeOverlapDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PARAGRAPH.value:
        return ParagraphDocumentChunking()
    else:
        raise Exception(f"Unknown chunking strategy: {chunking_strategy}")
