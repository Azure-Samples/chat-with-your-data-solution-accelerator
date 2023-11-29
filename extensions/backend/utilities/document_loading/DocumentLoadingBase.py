# Create an abstract class for document loading
from typing import List
from abc import ABC, abstractmethod
from ..common.SourceDocument import SourceDocument

class DocumentLoadingBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def load(self, document_url: str) -> List[SourceDocument]:
        pass