# Create an abstract class for orchestrator
import uuid
from typing import List
from abc import ABC, abstractmethod

class OrchestratorBase(ABC):
    def __init__(self) -> None:
        super().__init__()
        self.message_id = str(uuid.uuid4())
        self.tokens = {
            'prompt': 0,
            'completion': 0,
            'total': 0
        }
        print(f"New message id: {self.message_id} with tokens {self.tokens}")
    
    def log(self, prompt_tokens, completion_tokens):
        self.tokens['prompt'] += prompt_tokens
        self.tokens['completion'] += completion_tokens
        self.tokens['total'] += prompt_tokens + completion_tokens
    
    @abstractmethod
    def orchestrate(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        pass
    
    def handle_message(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        result = self.orchestrate(user_message, chat_history, **kwargs)
        # TODO: log tokens to App Insights
        return result
    