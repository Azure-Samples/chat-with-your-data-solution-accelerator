# Create an abstract class for tool
from abc import ABC, abstractmethod
from typing import List

class ToolBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def process_answer(self, question: str, answer: str, sources: List,**kwargs: dict) -> dict:        
        pass
    