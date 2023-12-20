import json
from datetime import datetime

from ..helpers.AzureSearchHelper import AzureSearchHelper


class ConversationLogger:
    """
    A class for logging conversations.

    Attributes:
        logger: The conversation logger instance.

    Methods:
        log(messages: list): Logs the user and assistant messages.
        log_user_message(messages: dict): Logs the user message.
        log_assistant_message(messages: dict): Logs the assistant message.
    """

    def __init__(self):
        self.logger = AzureSearchHelper().get_conversation_logger()

    def log(self, messages: list):
        """
        Logs the user and assistant messages.

        Args:
            messages (list): A list of messages.

        Returns:
            None
        """
        self.log_user_message(messages)
        self.log_assistant_message(messages)

    def log_user_message(self, messages: dict):
        """
        Logs the user message.

        Args:
            messages (dict): A dictionary containing the user message.

        Returns:
            None
        """
        text = ""
        metadata = {}
        for message in messages:
            if message['role'] == "user":
                metadata['type'] = message['role']
                metadata['conversation_id'] = message.get('conversation_id')
                metadata['created_at'] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                metadata['updated_at'] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                text = message['content']
        self.logger.add_texts(texts=[text], metadatas=[metadata])

    def log_assistant_message(self, messages: dict):
        """
        Logs the assistant message.

        Args:
            messages (dict): A dictionary containing the assistant message.

        Returns:
            None
        """
        text = ""
        metadata = {}
        try:
            metadata['conversation_id'] = set(
                filter(None, [message.get('conversation_id') for message in messages])).pop()
        except KeyError:
            metadata['conversation_id'] = None
        for message in messages:
            if message['role'] == "assistant":
                metadata['type'] = message['role']
                metadata['created_at'] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                metadata['updated_at'] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                text = message['content']
            elif message['role'] == "tool":
                metadata['sources'] = [source['id'] for source in json.loads(
                    message["content"]).get("citations", [])]
        self.logger.add_texts(texts=[text], metadatas=[metadata])
