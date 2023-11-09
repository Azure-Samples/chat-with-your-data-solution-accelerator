from typing import List
from langchain.docstore.document import Document
from ..orchestrator import get_orchestrator, OrchestrationSettings, OrchestrationStrategy

class Orchestrator:
    def __init__(self) -> None:
        pass
    
    def handle_message(self, user_message: str, chat_history: List[dict], conversation_id: str , orchestrator: OrchestrationSettings, **kwargs: dict) -> dict:
        orchestrator = get_orchestrator(orchestrator.strategy.value)
        if orchestrator is None:
            raise Exception(f"Unknown orchestration strategy: {orchestrator.strategy.value}")
        return orchestrator.handle_message(user_message, chat_history, conversation_id)
    