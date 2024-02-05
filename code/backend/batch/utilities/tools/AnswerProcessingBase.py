# Create an abstract class for tool
from abc import ABC, abstractmethod
from typing import List
from ..common.Answer import Answer

class AnswerProcessingBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def process_answer(self, answer: Answer,**kwargs: dict) -> Answer:        
        pass
    