# Create an abstract class for orchestrator
from typing import Optional
from abc import ABC, abstractmethod

class OrchestratorBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def orchestrate(self, question: str, functions: dict, system_message: Optional[dict], **kwargs: dict) -> dict:        
        pass
    