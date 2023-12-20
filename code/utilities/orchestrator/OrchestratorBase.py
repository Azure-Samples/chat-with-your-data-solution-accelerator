# Create an abstract class for orchestrator
from uuid import uuid4
from typing import List, Optional
from abc import ABC, abstractmethod
from ..loggers.TokenLogger import TokenLogger
from ..loggers.ConversationLogger import ConversationLogger
from ..helpers.ConfigHelper import ConfigHelper


class OrchestratorBase(ABC):
    """
    Base class for orchestrators in the chatbot system.
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigHelper.get_active_config_or_default()
        self.message_id = str(uuid4())
        self.tokens = {
            'prompt': 0,
            'completion': 0,
            'total': 0
        }
        print(f"New message id: {self.message_id} with tokens {self.tokens}")
        self.token_logger: TokenLogger = TokenLogger()
        self.conversation_logger: ConversationLogger = ConversationLogger()

    def log_tokens(self, prompt_tokens, completion_tokens):
        """
        Logs the number of tokens used in the conversation.

        Args:
            prompt_tokens (int): Number of tokens used for the prompt.
            completion_tokens (int): Number of tokens used for the completion.
        """
        self.tokens['prompt'] += prompt_tokens
        self.tokens['completion'] += completion_tokens
        self.tokens['total'] += prompt_tokens + completion_tokens

    @abstractmethod
    def orchestrate(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        """
        Orchestrates the chatbot conversation.

        Args:
            user_message (str): The user's message.
            chat_history (List[dict]): The chat history.
            **kwargs (dict): Additional keyword arguments.

        Returns:
            dict: The response from the chatbot.
        """

    def handle_message(self, user_message: str, chat_history: List[dict], conversation_id: Optional[str], **kwargs: Optional[dict]) -> dict:
        """
        Handles the user's message and logs the conversation.

        Args:
            user_message (str): The user's message.
            chat_history (List[dict]): The chat history.
            conversation_id (Optional[str]): The conversation ID.
            **kwargs (Optional[dict]): Additional keyword arguments.

        Returns:
            dict: The response from the chatbot.
        """
        result = self.orchestrate(user_message, chat_history, **kwargs)
        if self.config.logging.log_tokens:
            custom_dimensions = {
                "conversation_id": conversation_id,
                "message_id": self.message_id,
                "prompt_tokens": self.tokens['prompt'],
                "completion_tokens": self.tokens['completion'],
                "total_tokens": self.tokens['total']
            }
            self.token_logger.log(
                "Conversation", custom_dimensions=custom_dimensions)
        if self.config.logging.log_user_interactions:
            self.conversation_logger.log(messages=[
                            {"role": "user", "content": user_message, "conversation_id": conversation_id}] + result)
        return result
