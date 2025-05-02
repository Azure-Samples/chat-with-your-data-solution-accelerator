from .chunking_strategy import ChunkingStrategy
from .layout import LayoutDocumentChunking
from .page import PageDocumentChunking
from .fixed_size_overlap import FixedSizeOverlapDocumentChunking
from .paragraph import ParagraphDocumentChunking
from .json import JSONDocumentChunking


def get_document_chunker(chunking_strategy: str):
    if chunking_strategy == ChunkingStrategy.LAYOUT.value:
        return LayoutDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PAGE.value:
        return PageDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.FIXED_SIZE_OVERLAP.value:
        return FixedSizeOverlapDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.PARAGRAPH.value:
        return ParagraphDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.JSON.value:
        return JSONDocumentChunking()
    else:
        raise Exception(f"Unknown chunking strategy: {chunking_strategy}")
