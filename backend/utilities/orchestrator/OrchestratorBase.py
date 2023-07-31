# Create an abstract class for orchestrator
from typing import List
from abc import ABC, abstractmethod

class OrchestratorBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def orchestrate(self, question: str, chat_history: List[dict], **kwargs: dict) -> dict:        
        pass
    