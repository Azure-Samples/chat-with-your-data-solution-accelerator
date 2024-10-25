import os
import logging
from uuid import uuid4
from dotenv import load_dotenv
from flask import request, jsonify, Blueprint
from openai import AsyncAzureOpenAI
from backend.batch.utilities.chat_history.cosmosdb import CosmosConversationClient
from backend.batch.utilities.chat_history.auth_utils import (
    get_authenticated_user_details,
)
from backend.batch.utilities.helpers.config.config_helper import ConfigHelper
from azure.identity.aio import DefaultAzureCredential
from backend.batch.utilities.helpers.env_helper import EnvHelper

load_dotenv()
bp_chat_history_response = Blueprint("chat_history", __name__)
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())

env_helper: EnvHelper = EnvHelper()


def init_cosmosdb_client():
    cosmos_conversation_client = None
    config = ConfigHelper.get_active_config_or_default()
    if config.enable_chat_history:
        try:
            cosmos_endpoint = (
                f"https://{env_helper.AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/"
            )

            if not env_helper.AZURE_COSMOSDB_ACCOUNT_KEY:
                credential = DefaultAzureCredential()
            else:
                credential = env_helper.AZURE_COSMOSDB_ACCOUNT_KEY

            cosmos_conversation_client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=env_helper.AZURE_COSMOSDB_DATABASE,
                container_name=env_helper.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER,
                enable_message_feedback=env_helper.AZURE_COSMOSDB_ENABLE_FEEDBACK,
            )
        except Exception as e:
            logger.exception("Exception in CosmosDB initialization: %s", e)
            cosmos_conversation_client = None
            raise e
    else:
        logger.debug("CosmosDB not configured")

    return cosmos_conversation_client


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
        return (jsonify({"error": "Chat history is not avaliable"}), 400)

    try:
        offset = request.args.get("offset", 0)
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return (jsonify({"error": "database not available"}), 500)

        # get the conversations from cosmos
        conversations = await cosmos_conversation_client.get_conversations(
            user_id, offset=offset, limit=25
        )
        if not isinstance(conversations, list):
            return (
                jsonify({"error": f"No conversations for {user_id} were found"}),
                400,
            )

        return (jsonify(conversations), 200)

    except Exception as e:
        logger.exception("Exception in /list" + str(e))
        return (jsonify({"error": "Error While listing historical conversations"}), 500)


@bp_chat_history_response.route("/history/rename", methods=["POST"])
async def rename_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return (jsonify({"error": "Chat history is not avaliable"}), 400)
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

        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return (jsonify({"error": "database not available"}), 500)

        # get the conversation from cosmos
        conversation = await cosmos_conversation_client.get_conversation(
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

        # update the title
        title = request_json.get("title", None)
        if not title or title.strip() == "":
            return jsonify({"error": "title is required"}), 400
        conversation["title"] = title
        updated_conversation = await cosmos_conversation_client.upsert_conversation(
            conversation
        )
        return (jsonify(updated_conversation), 200)

    except Exception as e:
        logger.exception("Exception in /rename" + str(e))
        return (jsonify({"error": "Error renaming is fail"}), 500)


@bp_chat_history_response.route("/history/read", methods=["POST"])
async def get_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return (jsonify({"error": "Chat history is not avaliable"}), 400)

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

        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return (jsonify({"error": "database not available"}), 500)

        # get the conversation object and the related messages from cosmos
        conversation = await cosmos_conversation_client.get_conversation(
            user_id, conversation_id
        )
        # return the conversation id and the messages in the bot frontend format
        if not conversation:
            return (
                jsonify(
                    {
                        "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                    }
                ),
                400,
            )

        # get the messages for the conversation from cosmos
        conversation_messages = await cosmos_conversation_client.get_messages(
            user_id, conversation_id
        )

        # format the messages in the bot frontend format
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

        return (
            jsonify({"conversation_id": conversation_id, "messages": messages}),
            200,
        )
    except Exception as e:
        logger.exception("Exception in /read" + str(e))
        return (jsonify({"error": "Error while fetching history conversation"}), 500)


@bp_chat_history_response.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return (jsonify({"error": "Chat history is not avaliable"}), 400)

    try:
        # get the user id from the request headers
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

        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return (jsonify({"error": "database not available"}), 500)

        # delete the conversation messages from cosmos first
        await cosmos_conversation_client.delete_messages(conversation_id, user_id)

        # Now delete the conversation
        await cosmos_conversation_client.delete_conversation(user_id, conversation_id)

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
        logger.exception("Exception in /delete" + str(e))
        return (jsonify({"error": "Error while deleting history conversation"}), 500)


@bp_chat_history_response.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return (jsonify({"error": "Chat history is not avaliable"}), 400)

    try:
        # get the user id from the request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        # get conversations for user
        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return (jsonify({"error": "database not available"}), 500)

        conversations = await cosmos_conversation_client.get_conversations(
            user_id, offset=0, limit=None
        )
        if not conversations:
            return (
                jsonify({"error": f"No conversations for {user_id} were found"}),
                400,
            )

        # delete each conversation
        for conversation in conversations:
            # delete the conversation messages from cosmos first
            await cosmos_conversation_client.delete_messages(
                conversation["id"], user_id
            )

            # Now delete the conversation
            await cosmos_conversation_client.delete_conversation(
                user_id, conversation["id"]
            )

        return (
            jsonify(
                {
                    "message": f"Successfully deleted all conversation and messages for user {user_id} "
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception("Exception in /delete" + str(e))
        return (
            jsonify({"error": "Error while deleting all history conversation"}),
            500,
        )


@bp_chat_history_response.route("/history/update", methods=["POST"])
async def update_conversation():
    config = ConfigHelper.get_active_config_or_default()
    if not config.enable_chat_history:
        return (jsonify({"error": "Chat history is not avaliable"}), 400)

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    try:
        # check request for conversation_id
        request_json = request.get_json()
        conversation_id = request_json.get("conversation_id", None)
        if not conversation_id:
            return (jsonify({"error": "conversation_id is required"}), 400)

        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return jsonify({"error": "database not available"}), 500

        # check for the conversation_id, if the conversation is not set, we will create a new one
        conversation = await cosmos_conversation_client.get_conversation(
            user_id, conversation_id
        )
        if not conversation:
            title = await generate_title(request_json["messages"])
            conversation = await cosmos_conversation_client.create_conversation(
                user_id=user_id, conversation_id=conversation_id, title=title
            )
            conversation_id = conversation["id"]

        # Format the incoming message object in the "chat/completions" messages format then write it to the
        # conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[0]["role"] == "user":
            user_message = next(
                (
                    message
                    for message in reversed(messages)
                    if message["role"] == "user"
                ),
                None,
            )
            createdMessageValue = await cosmos_conversation_client.create_message(
                uuid=str(uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=user_message,
            )
            if createdMessageValue == "Conversation not found":
                return (jsonify({"error": "Conversation not found"}), 400)
        else:
            return (jsonify({"error": "User not found"}), 400)

        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                await cosmos_conversation_client.create_message(
                    uuid=str(uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            await cosmos_conversation_client.create_message(
                uuid=str(uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            return (jsonify({"error": "no conversationbot"}), 400)

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
        logger.exception("Exception in /update" + str(e))
        return (jsonify({"error": "Error while update the history conversation"}), 500)


@bp_chat_history_response.route("/history/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        ConfigHelper.get_active_config_or_default.cache_clear()
        config = ConfigHelper.get_active_config_or_default()
        chat_history_enabled = (
            config.enable_chat_history.lower() == "true"
            if isinstance(config.enable_chat_history, str)
            else config.enable_chat_history
        )
        return jsonify({"CHAT_HISTORY_ENABLED": chat_history_enabled}), 200
    except Exception as e:
        logger.exception("Exception in /frontend_settings" + str(e))
        return (jsonify({"error": "Error while getting frontend settings"}), 500)


async def generate_title(conversation_messages):
    title_prompt = "Summarize the conversation so far into a 4-word or less title. Do not use any quotation marks or punctuation. Do not include any other commentary or description."

    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages
        if msg["role"] == "user"
    ]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = init_openai_client()
        response = await azure_openai_client.chat.completions.create(
            model=env_helper.AZURE_OPENAI_MODEL,
            messages=messages,
            temperature=1,
            max_tokens=64,
        )

        title = response.choices[0].message.content
        return title
    except Exception:
        return messages[-2]["content"]
