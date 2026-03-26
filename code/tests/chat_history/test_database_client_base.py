import pytest
from abc import ABC
from typing import List, Dict, Any, Optional
from backend.batch.utilities.chat_history.database_client_base import (
    DatabaseClientBase,
)


class TestDatabaseClientBaseContract:
    """Test that DatabaseClientBase enforces the abstract contract"""

    def test_cannot_instantiate_abstract_class(self):
        """Test that DatabaseClientBase cannot be instantiated directly"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DatabaseClientBase()

    def test_is_abstract_base_class(self):
        """Test that DatabaseClientBase is an ABC"""
        assert issubclass(DatabaseClientBase, ABC)

    def test_missing_connect_raises_error(self):
        """Test that implementation without connect method cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_close_raises_error(self):
        """Test that implementation without close method cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_ensure_raises_error(self):
        """Test that implementation without ensure method cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_create_conversation_raises_error(self):
        """Test that implementation without create_conversation cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_upsert_conversation_raises_error(self):
        """Test that implementation without upsert_conversation cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_delete_conversation_raises_error(self):
        """Test that implementation without delete_conversation cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_delete_messages_raises_error(self):
        """Test that implementation without delete_messages cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_get_conversations_raises_error(self):
        """Test that implementation without get_conversations cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_get_conversation_raises_error(self):
        """Test that implementation without get_conversation cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_create_message_raises_error(self):
        """Test that implementation without create_message cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_update_message_feedback_raises_error(self):
        """Test that implementation without update_message_feedback cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def get_messages(self, user_id, conversation_id):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_missing_get_messages_raises_error(self):
        """Test that implementation without get_messages cannot be instantiated"""

        class IncompleteClient(DatabaseClientBase):
            async def connect(self):
                pass

            async def close(self):
                pass

            async def ensure(self):
                pass

            async def create_conversation(self, user_id, conversation_id, title=""):
                pass

            async def upsert_conversation(self, conversation):
                pass

            async def delete_conversation(self, user_id, conversation_id):
                pass

            async def delete_messages(self, conversation_id, user_id):
                pass

            async def get_conversations(
                self, user_id, limit, sort_order="DESC", offset=0
            ):
                pass

            async def get_conversation(self, user_id, conversation_id):
                pass

            async def create_message(self, uuid, conversation_id, user_id, input_message):
                pass

            async def update_message_feedback(self, user_id, message_id, feedback):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    @pytest.mark.asyncio
    async def test_complete_implementation_can_be_instantiated(self):
        """Test that a complete implementation of DatabaseClientBase can be instantiated"""

        class CompleteClient(DatabaseClientBase):
            async def connect(self):
                return True

            async def close(self):
                return True

            async def ensure(self):
                return True, "Connected"

            async def create_conversation(
                self, user_id: str, conversation_id: str, title: str = ""
            ) -> bool:
                return True

            async def upsert_conversation(self, conversation: Dict[str, Any]) -> bool:
                return True

            async def delete_conversation(
                self, user_id: str, conversation_id: str
            ) -> bool:
                return True

            async def delete_messages(
                self, conversation_id: str, user_id: str
            ) -> List[Dict[str, Any]]:
                return []

            async def get_conversations(
                self,
                user_id: str,
                limit: int,
                sort_order: str = "DESC",
                offset: int = 0,
            ) -> List[Dict[str, Any]]:
                return []

            async def get_conversation(
                self, user_id: str, conversation_id: str
            ) -> Optional[Dict[str, Any]]:
                return None

            async def create_message(
                self,
                uuid: str,
                conversation_id: str,
                user_id: str,
                input_message: Dict[str, Any],
            ) -> bool:
                return True

            async def update_message_feedback(
                self, user_id: str, message_id: str, feedback: str
            ) -> bool:
                return True

            async def get_messages(
                self, user_id: str, conversation_id: str
            ) -> List[Dict[str, Any]]:
                return []

        # Should be able to instantiate without errors
        client = CompleteClient()
        assert isinstance(client, DatabaseClientBase)
        assert isinstance(client, CompleteClient)

        # Verify all methods are callable
        await client.connect()
        await client.close()
        await client.ensure()
        await client.create_conversation("user1", "conv1", "Test")
        await client.upsert_conversation({"id": "conv1"})
        await client.delete_conversation("user1", "conv1")
        await client.delete_messages("conv1", "user1")
        await client.get_conversations("user1", 10)
        await client.get_conversation("user1", "conv1")
        await client.create_message("msg1", "conv1", "user1", {"content": "test"})
        await client.update_message_feedback("user1", "msg1", "positive")
        await client.get_messages("user1", "conv1")


class TestDatabaseClientBaseMethodSignatures:
    """Test that DatabaseClientBase defines correct method signatures"""

    def test_connect_signature(self):
        """Test connect method has correct signature"""
        assert hasattr(DatabaseClientBase, "connect")
        assert callable(getattr(DatabaseClientBase, "connect"))

    def test_close_signature(self):
        """Test close method has correct signature"""
        assert hasattr(DatabaseClientBase, "close")
        assert callable(getattr(DatabaseClientBase, "close"))

    def test_ensure_signature(self):
        """Test ensure method has correct signature"""
        assert hasattr(DatabaseClientBase, "ensure")
        assert callable(getattr(DatabaseClientBase, "ensure"))

    def test_create_conversation_signature(self):
        """Test create_conversation method has correct signature"""
        assert hasattr(DatabaseClientBase, "create_conversation")
        assert callable(getattr(DatabaseClientBase, "create_conversation"))

    def test_upsert_conversation_signature(self):
        """Test upsert_conversation method has correct signature"""
        assert hasattr(DatabaseClientBase, "upsert_conversation")
        assert callable(getattr(DatabaseClientBase, "upsert_conversation"))

    def test_delete_conversation_signature(self):
        """Test delete_conversation method has correct signature"""
        assert hasattr(DatabaseClientBase, "delete_conversation")
        assert callable(getattr(DatabaseClientBase, "delete_conversation"))

    def test_delete_messages_signature(self):
        """Test delete_messages method has correct signature"""
        assert hasattr(DatabaseClientBase, "delete_messages")
        assert callable(getattr(DatabaseClientBase, "delete_messages"))

    def test_get_conversations_signature(self):
        """Test get_conversations method has correct signature"""
        assert hasattr(DatabaseClientBase, "get_conversations")
        assert callable(getattr(DatabaseClientBase, "get_conversations"))

    def test_get_conversation_signature(self):
        """Test get_conversation method has correct signature"""
        assert hasattr(DatabaseClientBase, "get_conversation")
        assert callable(getattr(DatabaseClientBase, "get_conversation"))

    def test_create_message_signature(self):
        """Test create_message method has correct signature"""
        assert hasattr(DatabaseClientBase, "create_message")
        assert callable(getattr(DatabaseClientBase, "create_message"))

    def test_update_message_feedback_signature(self):
        """Test update_message_feedback method has correct signature"""
        assert hasattr(DatabaseClientBase, "update_message_feedback")
        assert callable(getattr(DatabaseClientBase, "update_message_feedback"))

    def test_get_messages_signature(self):
        """Test get_messages method has correct signature"""
        assert hasattr(DatabaseClientBase, "get_messages")
        assert callable(getattr(DatabaseClientBase, "get_messages"))
