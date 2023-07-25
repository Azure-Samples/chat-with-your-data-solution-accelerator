# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from langchain.docstore.document import Document
from .Strategies import ChunkingSettings

class DocumentChunkingBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def chunk(self, documents: List[Document], chunking: ChunkingSettings) -> List[Document]:        
        pass