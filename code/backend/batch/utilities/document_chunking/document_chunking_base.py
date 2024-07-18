# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from ..common.source_document import SourceDocument
from .chunking_strategy import ChunkingSettings


class DocumentChunkingBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        pass
