from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class DatabaseClientBase(ABC):
    @abstractmethod
    async def connect(self):
        """Establish a connection to the database."""
        pass

    @abstractmethod
    async def close(self):
        """Close the connection to the database."""
        pass

    @abstractmethod
    async def ensure(self):
        """Verify that the database and required tables/collections exist."""
        pass

    @abstractmethod
    async def create_conversation(
        self, user_id: str, conversation_id: str, title: str = ""
    ) -> bool:
        """Create a new conversation entry."""
        pass

    @abstractmethod
    async def upsert_conversation(self, conversation: Dict[str, Any]) -> bool:
        """Update or insert a conversation entry."""
        pass

    @abstractmethod
    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a specific conversation."""
        pass

    @abstractmethod
    async def delete_messages(
        self, conversation_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Delete all messages associated with a conversation."""
        pass

    @abstractmethod
    async def get_conversations(
        self, user_id: str, limit: int, sort_order: str = "DESC", offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve a list of conversations for a user."""
        pass

    @abstractmethod
    async def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific conversation by ID."""
        pass

    @abstractmethod
    async def create_message(
        self,
        uuid: str,
        conversation_id: str,
        user_id: str,
        input_message: Dict[str, Any],
    ) -> bool:
        """Create a new message within a conversation."""
        pass

    @abstractmethod
    async def update_message_feedback(
        self, user_id: str, message_id: str, feedback: str
    ) -> bool:
        """Update feedback for a specific message."""
        pass

    @abstractmethod
    async def get_messages(
        self, user_id: str, conversation_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve all messages within a conversation."""
        pass
