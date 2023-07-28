# Create an abstract class for tool
from abc import ABC, abstractmethod

class ToolBase(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def action(self, input: dict, **kwargs: dict) -> dict:        
        pass
    