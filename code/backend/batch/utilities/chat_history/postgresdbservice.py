import logging
import asyncpg
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential

from .database_client_base import DatabaseClientBase

logger = logging.getLogger(__name__)


class PostgresConversationClient(DatabaseClientBase):

    def __init__(
        self, user: str, host: str, database: str, enable_message_feedback: bool = False
    ):
        self.user = user
        self.host = host
        self.database = database
        self.enable_message_feedback = enable_message_feedback
        self.conn = None

    async def connect(self):
        try:
            credential = DefaultAzureCredential()
            token = credential.get_token(
                "https://ossrdbms-aad.database.windows.net/.default"
            ).token
            self.conn = await asyncpg.connect(
                user=self.user,
                host=self.host,
                database=self.database,
                password=token,
                port=5432,
                ssl="require",
            )
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
            raise

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def ensure(self):
        if not self.conn:
            return False, "PostgreSQL client not initialized correctly"
        return True, "PostgreSQL client initialized successfully"

    async def create_conversation(self, conversation_id, user_id, title=""):
        utc_now = datetime.now(timezone.utc)
        createdAt = utc_now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        query = """
            INSERT INTO conversations (id, conversation_id, type, "createdAt", "updatedAt", user_id, title)
            VALUES ($1, $2, 'conversation', $3, $3, $4, $5)
            RETURNING *
        """
        conversation = await self.conn.fetchrow(
            query, conversation_id, conversation_id, createdAt, user_id, title
        )
        return dict(conversation) if conversation else False

    async def upsert_conversation(self, conversation):
        query = """
            INSERT INTO conversations (id, conversation_id, type, "createdAt", "updatedAt", user_id, title)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                "updatedAt" = EXCLUDED."updatedAt",
                title = EXCLUDED.title
            RETURNING *
        """
        updated_conversation = await self.conn.fetchrow(
            query,
            conversation["id"],
            conversation["conversation_id"],
            conversation["type"],
            conversation["createdAt"],
            conversation["updatedAt"],
            conversation["user_id"],
            conversation["title"],
        )
        return dict(updated_conversation) if updated_conversation else False

    async def delete_conversation(self, user_id, conversation_id):
        query = "DELETE FROM conversations WHERE conversation_id = $1 AND user_id = $2"
        await self.conn.execute(query, conversation_id, user_id)
        return True

    async def delete_messages(self, conversation_id, user_id):
        query = "DELETE FROM messages WHERE conversation_id = $1 AND user_id = $2 RETURNING *"
        messages = await self.conn.fetch(query, conversation_id, user_id)
        return [dict(message) for message in messages]

    async def get_conversations(self, user_id, limit=None, sort_order="DESC", offset=0):
        try:
            offset = int(offset)  # Ensure offset is an integer
        except ValueError:
            raise ValueError("Offset must be an integer.")
        # Base query without LIMIT and OFFSET
        query = f"""
            SELECT * FROM conversations
            WHERE user_id = $1 AND type = 'conversation'
            ORDER BY "updatedAt" {sort_order}
        """
        # Append LIMIT and OFFSET to the query if limit is specified
        if limit is not None:
            try:
                limit = int(limit)  # Ensure limit is an integer
                query += " LIMIT $2 OFFSET $3"
                # Fetch records with LIMIT and OFFSET
                conversations = await self.conn.fetch(query, user_id, limit, offset)
            except ValueError:
                raise ValueError("Limit must be an integer.")
        else:
            # Fetch records without LIMIT and OFFSET
            conversations = await self.conn.fetch(query, user_id)
        return [dict(conversation) for conversation in conversations]

    async def get_conversation(self, user_id, conversation_id):
        query = "SELECT * FROM conversations WHERE id = $1 AND user_id = $2 AND type = 'conversation'"
        conversation = await self.conn.fetchrow(query, conversation_id, user_id)
        return dict(conversation) if conversation else None

    async def create_message(self, uuid, conversation_id, user_id, input_message: dict):
        message_id = uuid
        utc_now = datetime.now(timezone.utc)
        createdAt = utc_now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        query = """
            INSERT INTO messages (id, type, "createdAt", "updatedAt", user_id, conversation_id, role, content, feedback)
            VALUES ($1, 'message', $2, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        feedback = "" if self.enable_message_feedback else None
        message = await self.conn.fetchrow(
            query,
            message_id,
            createdAt,
            user_id,
            conversation_id,
            input_message["role"],
            input_message["content"],
            feedback,
        )

        if message:
            update_query = 'UPDATE conversations SET "updatedAt" = $1 WHERE id = $2 AND user_id = $3 RETURNING *'
            await self.conn.execute(update_query, createdAt, conversation_id, user_id)
            return dict(message)
        else:
            return False

    async def update_message_feedback(self, user_id, message_id, feedback):
        query = "UPDATE messages SET feedback = $1 WHERE id = $2 AND user_id = $3 RETURNING *"
        message = await self.conn.fetchrow(query, feedback, message_id, user_id)
        return dict(message) if message else False

    async def get_messages(self, user_id, conversation_id):
        query = 'SELECT * FROM messages WHERE conversation_id = $1 AND user_id = $2 ORDER BY "createdAt" ASC'
        messages = await self.conn.fetch(query, conversation_id, user_id)
        return [dict(message) for message in messages]
