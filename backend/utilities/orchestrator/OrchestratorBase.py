# Create an abstract class for orchestrator
from uuid import uuid4
from typing import List
from abc import ABC, abstractmethod
from ..loggers.Logger import Logger

class OrchestratorBase(ABC):
    def __init__(self) -> None:
        super().__init__()
        self.message_id = str(uuid4())
        self.tokens = {
            'prompt': 0,
            'completion': 0,
            'total': 0
        }
        print(f"New message id: {self.message_id} with tokens {self.tokens}")
        self.logger : Logger = Logger(name=__name__)
    
    def log(self, prompt_tokens, completion_tokens):
        self.tokens['prompt'] += prompt_tokens
        self.tokens['completion'] += completion_tokens
        self.tokens['total'] += prompt_tokens + completion_tokens
    
    @abstractmethod
    def orchestrate(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        pass
    
    def handle_message(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        result = self.orchestrate(user_message, chat_history, **kwargs)
        custom_dimensions = {
            "message_id": self.message_id,
            "prompt_tokens": self.tokens['prompt'],
            "completion_tokens": self.tokens['completion'],
            "total_tokens": self.tokens['total']
        }
        self.logger.log("Conversation", custom_dimensions=custom_dimensions)                
        return result
    