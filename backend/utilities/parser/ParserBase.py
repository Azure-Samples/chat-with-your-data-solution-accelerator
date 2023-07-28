# Create an abstract class for parser
from abc import ABC, abstractmethod
from typing import List

class ParserBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def parse(self, input: dict, **kwargs: dict) -> List[dict]:        
        pass
    