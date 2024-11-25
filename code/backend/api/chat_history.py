import os
import logging
from uuid import uuid4
from dotenv import load_dotenv
from flask import request, jsonify, Blueprint
from openai import AsyncAzureOpenAI
from backend.batch.utilities.chat_history.auth_utils import (
    get_authenticated_user_details,
)
from backend.batch.utilities.helpers.config.config_helper import ConfigHelper
from backend.batch.utilities.helpers.env_helper import EnvHelper
from backend.batch.utilities.chat_history.database_factory import DatabaseFactory

load_dotenv()
bp_chat_history_response = Blueprint("chat_history", __name__)
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())

env_helper: EnvHelper = EnvHelper()


def init_database_client():
    try:
        conversation_client = DatabaseFactory.get_conversation_client()
        return conversation_client
    except Exception as e:
        logger.exception("Exception in database initialization: %s", e)
        raise e


def init_openai_client():
    try:
        if env_helper.is_auth_type_keys():
            azure_openai_client = AsyncAzureOpenAI(
                azure_endpoint=env_helper.AZURE_OPENAI_ENDPOINT,
                api_version=env_helper.AZURE_OPENAI_API_VERSION,
                api_key=env_helper.AZURE_OPENAI_API_KEY,
            )
        else:
            azure_openai_client = AsyncAzureOpenAI(
                azure_endpoint=env_helper.AZURE_OPENAI_ENDPOINT,
                api_version=env_helper.AZURE_OPENAI_API_VERSION,
                azure_ad_token_provider=env_helper.AZURE_TOKEN_PROVIDER,
            )
        return azure_openai_client
    except Exception as e:
        logging.exception("Exception in Azure OpenAI initialization: %s", e)
        raise e


@bp_chat_history_response.route("/history/list", methods=["GET"])
async def list_conversations():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        offset = request.args.get("offset", 0)
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500

        await conversation_client.connect()
        try:
            conversations = await conversation_client.get_conversations(
                user_id, offset=offset, limit=25
            )
            if not isinstance(conversations, list):
                return (
                    jsonify({"error": f"No conversations for {user_id} were found"}),
                    404,
                )

            return jsonify(conversations), 200
        except Exception as e:
            logger.exception(f"Error fetching conversations: {e}")
            raise
        finally:
            await conversation_client.close()

    except Exception as e:
        logger.exception(f"Exception in /history/list: {e}")
        return jsonify({"error": "Error while listing historical conversations"}), 500


@bp_chat_history_response.route("/history/rename", methods=["POST"])
async def rename_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        # check request for conversation_id
        request_json = request.get_json()
        conversation_id = request_json.get("conversation_id", None)

        if not conversation_id:
            return (jsonify({"error": "conversation_id is required"}), 400)

        title = request_json.get("title", None)
        if not title or title.strip() == "":
            return jsonify({"error": "A non-empty title is required"}), 400

        # Initialize and connect to the database client
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500

        await conversation_client.connect()
        try:
            # Retrieve conversation from database
            conversation = await conversation_client.get_conversation(
                user_id, conversation_id
            )
            if not conversation:
                return (
                    jsonify(
                        {
                            "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                        }
                    ),
                    400,
                )

            # Update the title and save changes
            conversation["title"] = title
            updated_conversation = await conversation_client.upsert_conversation(
                conversation
            )
            return jsonify(updated_conversation), 200
        except Exception as e:
            logger.exception(
                f"Error updating conversation: user_id={user_id}, conversation_id={conversation_id}, error={e}"
            )
            raise
        finally:
            await conversation_client.close()
    except Exception as e:
        logger.exception(f"Exception in /history/rename: {e}")
        return jsonify({"error": "Error while renaming conversation"}), 500


@bp_chat_history_response.route("/history/read", methods=["POST"])
async def get_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        # check request for conversation_id
        request_json = request.get_json()
        conversation_id = request_json.get("conversation_id", None)
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        # Initialize and connect to the database client
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500

        await conversation_client.connect()
        try:
            # Retrieve conversation
            conversation = await conversation_client.get_conversation(
                user_id, conversation_id
            )
            if not conversation:
                return (
                    jsonify(
                        {
                            "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                        }
                    ),
                    400,
                )

            # Fetch conversation messages
            conversation_messages = await conversation_client.get_messages(
                user_id, conversation_id
            )
            messages = [
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "createdAt": msg["createdAt"],
                    "feedback": msg.get("feedback"),
                }
                for msg in conversation_messages
            ]

            # Return formatted conversation and messages
            return (
                jsonify({"conversation_id": conversation_id, "messages": messages}),
                200,
            )
        except Exception as e:
            logger.exception(
                f"Error fetching conversation or messages: user_id={user_id}, conversation_id={conversation_id}, error={e}"
            )
            raise
        finally:
            await conversation_client.close()

    except Exception as e:
        logger.exception(f"Exception in /history/read: {e}")
        return jsonify({"error": "Error while fetching conversation history"}), 500


@bp_chat_history_response.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        # Get the user ID from the request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        # check request for conversation_id
        request_json = request.get_json()
        conversation_id = request_json.get("conversation_id", None)
        if not conversation_id:
            return (
                jsonify(
                    {
                        "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                    }
                ),
                400,
            )

        # Initialize and connect to the database client
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500

        await conversation_client.connect()
        try:
            # Delete conversation messages from database
            await conversation_client.delete_messages(conversation_id, user_id)

            # Delete the conversation itself
            await conversation_client.delete_conversation(user_id, conversation_id)

            return (
                jsonify(
                    {
                        "message": "Successfully deleted conversation and messages",
                        "conversation_id": conversation_id,
                    }
                ),
                200,
            )
        except Exception as e:
            logger.exception(
                f"Error deleting conversation: user_id={user_id}, conversation_id={conversation_id}, error={e}"
            )
            raise
        finally:
            await conversation_client.close()

    except Exception as e:
        logger.exception(f"Exception in /history/delete: {e}")
        return jsonify({"error": "Error while deleting conversation history"}), 500


@bp_chat_history_response.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    config = ConfigHelper.get_active_config_or_default()

    # Check if chat history is available
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        # Get the user ID from the request headers (ensure authentication is successful)
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        # Initialize the database client
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500

        await conversation_client.connect()
        try:
            # Get all conversations for the user
            conversations = await conversation_client.get_conversations(
                user_id, offset=0, limit=None
            )
            if not conversations:
                return (
                    jsonify({"error": f"No conversations found for user {user_id}"}),
                    400,
                )

            # Delete each conversation and its associated messages
            for conversation in conversations:
                try:
                    # Delete messages associated with the conversation
                    await conversation_client.delete_messages(
                        conversation["id"], user_id
                    )

                    # Delete the conversation itself
                    await conversation_client.delete_conversation(
                        user_id, conversation["id"]
                    )

                except Exception as e:
                    # Log and continue with the next conversation if one fails
                    logger.exception(
                        f"Error deleting conversation {conversation['id']} for user {user_id}: {e}"
                    )
                    continue
            return (
                jsonify(
                    {
                        "message": f"Successfully deleted all conversations and messages for user {user_id}"
                    }
                ),
                200,
            )
        except Exception as e:
            logger.exception(
                f"Error deleting all conversations for user {user_id}: {e}"
            )
            raise
        finally:
            await conversation_client.close()

    except Exception as e:
        logger.exception(f"Exception in /history/delete_all: {e}")
        return jsonify({"error": "Error while deleting all conversation history"}), 500


@bp_chat_history_response.route("/history/update", methods=["POST"])
async def update_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return jsonify({"error": "Chat history is not available"}), 400

    try:
        # Get user details from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        request_json = request.get_json()
        conversation_id = request_json.get("conversation_id", None)
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        messages = request_json["messages"]
        if not messages or len(messages) == 0:
            return jsonify({"error": "Messages are required"}), 400

        # Initialize conversation client
        conversation_client = init_database_client()
        if not conversation_client:
            return jsonify({"error": "Database not available"}), 500
        await conversation_client.connect()
        try:
            # Get or create the conversation
            conversation = await conversation_client.get_conversation(
                user_id, conversation_id
            )
            if not conversation:
                title = await generate_title(messages)
                conversation = await conversation_client.create_conversation(
                    user_id=user_id, conversation_id=conversation_id, title=title
                )

            # Process and save user and assistant messages
            # Process user message
            if messages[0]["role"] == "user":
                user_message = next(
                    (msg for msg in reversed(messages) if msg["role"] == "user"), None
                )
                if not user_message:
                    return jsonify({"error": "User message not found"}), 400

                created_message = await conversation_client.create_message(
                    uuid=str(uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=user_message,
                )
                if created_message == "Conversation not found":
                    return jsonify({"error": "Conversation not found"}), 400

            # Process assistant and tool messages if available
            if messages[-1]["role"] == "assistant":
                if len(messages) > 1 and messages[-2].get("role") == "tool":
                    # Write the tool message first if it exists
                    await conversation_client.create_message(
                        uuid=str(uuid4()),
                        conversation_id=conversation_id,
                        user_id=user_id,
                        input_message=messages[-2],
                    )
                # Write the assistant message
                await conversation_client.create_message(
                    uuid=str(uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-1],
                )
            else:
                return jsonify({"error": "No assistant message found"}), 400

            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "title": conversation["title"],
                            "date": conversation["updatedAt"],
                            "conversation_id": conversation["id"],
                        },
                    }
                ),
                200,
            )
        except Exception as e:
            logger.exception(
                f"Error updating conversation or messages: user_id={user_id}, conversation_id={conversation_id}, error={e}"
            )
            raise
        finally:
            await conversation_client.close()

    except Exception as e:
        logger.exception(f"Exception in /history/update: {e}")
        return jsonify({"error": "Error while updating the conversation history"}), 500


@bp_chat_history_response.route("/history/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        # Clear the cache for the config helper method
        ConfigHelper.get_active_config_or_default.cache_clear()

        # Retrieve active config
        config = ConfigHelper.get_active_config_or_default()

        # Ensure `enable_chat_history` is processed correctly
        if isinstance(config.enable_chat_history, str):
            chat_history_enabled = config.enable_chat_history.strip().lower() == "true"
        else:
            chat_history_enabled = bool(config.enable_chat_history)

        return jsonify({"CHAT_HISTORY_ENABLED": chat_history_enabled}), 200

    except Exception as e:
        logger.exception(f"Exception in /history/frontend_settings: {e}")
        return jsonify({"error": "Error while getting frontend settings"}), 500


async def generate_title(conversation_messages):
    title_prompt = "Summarize the conversation so far into a 4-word or less title. Do not use any quotation marks or punctuation. Do not include any other commentary or description."

    # Filter only the user messages, but consider including system or assistant context if necessary
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages
        if msg["role"] == "user"
    ]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = init_openai_client()

        # Create a chat completion with the Azure OpenAI client
        response = await azure_openai_client.chat.completions.create(
            model=env_helper.AZURE_OPENAI_MODEL,
            messages=messages,
            temperature=1,
            max_tokens=64,
        )

        # Ensure response contains valid choices and content
        if response and response.choices and len(response.choices) > 0:
            title = response.choices[0].message.content.strip()
            return title
        else:
            raise ValueError("No valid choices in response")

    except Exception as e:
        logger.exception(f"Error generating title: {str(e)}")
        # Fallback: return the content of the second to last message if something goes wrong
        return messages[-2]["content"] if len(messages) > 1 else "Untitled"
