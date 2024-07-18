from enum import Enum


class ChunkingStrategy(Enum):
    LAYOUT = "layout"
    PAGE = "page"
    FIXED_SIZE_OVERLAP = "fixed_size_overlap"
    PARAGRAPH = "paragraph"
    MOCK = "mock"
    SHAREPOINT_PAGE = "sharepoint_page"


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
    elif chunking_strategy == ChunkingStrategy.MOCK.value:
        from .Empty import MockedDocumentChunking

        return MockedDocumentChunking()
    elif chunking_strategy == ChunkingStrategy.SHAREPOINT_PAGE.value:
        from .SharepointPageDocumentChunking import SharepointPageDocumentChunking

        return SharepointPageDocumentChunking()
    else:
        raise Exception(f"Unknown chunking strategy: {chunking_strategy}")


class ChunkingSettings:
    def __init__(self, chunking: dict):
        self.chunking_strategy = ChunkingStrategy(chunking["strategy"])
        self.chunk_size = chunking["size"]
        self.chunk_overlap = chunking["overlap"]
