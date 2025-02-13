from enum import Enum


class ChunkingStrategy(Enum):
    LAYOUT = "layout"
    PAGE = "page"
    FIXED_SIZE_OVERLAP = "fixed_size_overlap"
    PARAGRAPH = "paragraph"
    JSON = "json"


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
