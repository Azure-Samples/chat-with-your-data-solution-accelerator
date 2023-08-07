# Create an abstract class for parser
from abc import ABC, abstractmethod
from typing import List
from .SourceDocument import SourceDocument

class ParserBase(ABC):
    def __init__(self) -> None:
        pass
       
    @abstractmethod
    def parse(self, question: str, answer: str, source_documents: List[SourceDocument], **kwargs: dict) -> List[dict]:        
        pass
    