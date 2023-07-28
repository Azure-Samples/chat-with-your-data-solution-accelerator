# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from ..parser.SourceDocument import SourceDocument
from .Strategies import ChunkingSettings

class DocumentChunkingBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def chunk(self, documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:        
        pass