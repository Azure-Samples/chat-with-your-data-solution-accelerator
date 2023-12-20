from typing import List
from langchain.docstore.document import Document
from ..orchestrator import get_orchestrator, OrchestrationSettings, OrchestrationStrategy


class Orchestrator:
    """
    The Orchestrator class handles the orchestration of the conversation flow.

    Attributes:
        None

    Methods:
        handle_message: Handles the user message and orchestrates the conversation flow.
    """
    
    def __init__(self) -> None:
        pass

    def handle_message(self, user_message: str, chat_history: List[dict], conversation_id: str, orchestrator: OrchestrationSettings, **kwargs: dict) -> dict:
        """
        Handles the user message and orchestrates the conversation flow.

        Args:
            user_message (str): The user's message.
            chat_history (List[dict]): The chat history.
            conversation_id (str): The conversation ID.
            orchestrator (OrchestrationSettings): The orchestrator settings.
            **kwargs (dict): Additional keyword arguments.

        Returns:
            dict: The response from the orchestrator.
        """
        orchestrator = get_orchestrator(orchestrator.strategy.value)
        if orchestrator is None:
            raise ValueError(f"Unknown orchestration strategy: {orchestrator.strategy.value}")
        return orchestrator.handle_message(user_message, chat_history, conversation_id)
