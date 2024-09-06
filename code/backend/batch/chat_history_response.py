import os
import azure.functions as func
import logging
import json
from uuid import uuid4
from dotenv import load_dotenv

from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.orchestrator_helper import Orchestrator
from utilities.helpers.config.config_helper import ConfigHelper
from code.backend.batch.utilities.chat_history.cosmosdb import CosmosConversationClient
from utilities.auth.auth_utils import get_authenticated_user_details
import asyncio
from azure.identity.aio import DefaultAzureCredential

load_dotenv()
bp_chat_history_response = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())

# Chat History CosmosDB Integration Settings
AZURE_COSMOSDB_DATABASE = os.environ.get("AZURE_COSMOSDB_DATABASE")
AZURE_COSMOSDB_ACCOUNT = os.environ.get("AZURE_COSMOSDB_ACCOUNT")
AZURE_COSMOSDB_CONVERSATIONS_CONTAINER = os.environ.get(
    "AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"
)
AZURE_COSMOSDB_ACCOUNT_KEY = os.environ.get("AZURE_COSMOSDB_ACCOUNT_KEY")
AZURE_COSMOSDB_ENABLE_FEEDBACK = (
    os.environ.get("AZURE_COSMOSDB_ENABLE_FEEDBACK", "false").lower() == "true"
)
CHAT_HISTORY_ENABLED = os.environ.get("CHAT_HISTORY_ENABLED", "false").lower() == "true"


def init_cosmosdb_client():
    cosmos_conversation_client = None
    if CHAT_HISTORY_ENABLED:
        try:
            cosmos_endpoint = (
                f"https://{AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/"
            )

            if not AZURE_COSMOSDB_ACCOUNT_KEY:
                credential = DefaultAzureCredential()
            else:
                credential = AZURE_COSMOSDB_ACCOUNT_KEY

            cosmos_conversation_client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=AZURE_COSMOSDB_DATABASE,
                container_name=AZURE_COSMOSDB_CONVERSATIONS_CONTAINER,
                enable_message_feedback=AZURE_COSMOSDB_ENABLE_FEEDBACK,
            )
        except Exception as e:
            logger.exception("Exception in CosmosDB initialization")
            cosmos_conversation_client = None
            raise e
    else:
        logger.debug("CosmosDB not configured")

    return cosmos_conversation_client


@bp_chat_history_response.route("/history/list", methods=[func.HttpMethod.GET])
async def list_conversations(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )
    offset = request.args.get("offset", 0)
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        ## get the conversations from cosmos
        conversations = await cosmos_conversation_client.get_conversations(
            user_id, offset=offset, limit=25
        )
        if not isinstance(conversations, list):
            return func.HttpResponse(
                json.dumps({"error": f"No conversations for {user_id} were found"}),
                status_code=400,
            )

        return func.HttpResponse(json.dumps(conversations), 200)

    except Exception as e:
        logger.exception("Exception in /history/list")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/rename", methods=[func.HttpMethod.POST])
async def rename_conversation(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return func.HttpResponse(
            json.dumps({"error": "conversation_id is required"}), status_code=400
        )

    ## make sure cosmos is configured
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        ## get the conversation from cosmos
        conversation = await cosmos_conversation_client.get_conversation(
            user_id, conversation_id
        )
        if not conversation:
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                    }
                ),
                status_code=400,
            )

        ## update the title
        title = request_json.get("title", None)
        if not title:
            return func.HttpResponse(
                json.dumps({"error": "title is required"}), status_code=400
            )
        conversation["title"] = title
        updated_conversation = await cosmos_conversation_client.upsert_conversation(
            conversation
        )
        return func.HttpResponse(json.dumps(updated_conversation), 200)

    except Exception as e:
        logger.exception("Exception in /history/rename")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/read", methods=[func.HttpMethod.POST])
async def get_conversation(request: func.HttpRequest) -> func.HttpResponse:

    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return func.HttpResponse(
            json.dumps({"error": "conversation_id is required"}), status_code=400
        )

    ## make sure cosmos is configured
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        ## get the conversation object and the related messages from cosmos
        conversation = await cosmos_conversation_client.get_conversation(
            user_id, conversation_id
        )
        ## return the conversation id and the messages in the bot frontend format
        if not conversation:
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                    }
                ),
                status_code=400,
            )

        # get the messages for the conversation from cosmos
        conversation_messages = await cosmos_conversation_client.get_messages(
            user_id, conversation_id
        )

        ## format the messages in the bot frontend format
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

        return func.HttpResponse(
            json.dumps({"conversation_id": conversation_id, "messages": messages}), 200
        )
    except Exception as e:
        logger.exception("Exception in /history/read")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/delete", methods=[func.HttpMethod.DELETE])
async def delete_conversation(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )
    ## get the user id from the request headers
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                    }
                ),
                status_code=400,
            )

        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        ## delete the conversation messages from cosmos first
        deleted_messages = await cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        ## Now delete the conversation
        deleted_conversation = await cosmos_conversation_client.delete_conversation(
            user_id, conversation_id
        )

        return func.HttpResponse(
            json.dumps(
                {
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logger.exception("Exception in /history/delete")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/delete_all", methods=[func.HttpMethod.DELETE])
async def delete_all_conversations(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )
    ## get the user id from the request headers
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    # get conversations for user
    try:
        ## make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        conversations = await cosmos_conversation_client.get_conversations(
            user_id, offset=0, limit=None
        )
        if not conversations:
            return func.HttpResponse(
                json.dumps({"error": f"No conversations for {user_id} were found"}),
                status_code=400,
            )

        # delete each conversation
        for conversation in conversations:
            ## delete the conversation messages from cosmos first
            deleted_messages = await cosmos_conversation_client.delete_messages(
                conversation["id"], user_id
            )

            ## Now delete the conversation
            deleted_conversation = await cosmos_conversation_client.delete_conversation(
                user_id, conversation["id"]
            )

        return func.HttpResponse(
            json.dumps(
                {
                    "message": f"Successfully deleted all conversation and messages for user {user_id} "
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception("Exception in /history/delete")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/generate", methods=[func.HttpMethod.POST])
async def add_conversation(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        ## make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )
        # check for the conversation_id, if the conversation is not set, we will create a new one
        history_metadata = {}
        if not conversation_id:
            title = "New Message"  ##TODO GENERATE TITLE ##await generate_title(request_json["messages"])
            conversation_dict = await cosmos_conversation_client.create_conversation(
                user_id=user_id, title=title
            )
            conversation_id = conversation_dict["id"]
            history_metadata["title"] = title
            history_metadata["date"] = conversation_dict["createdAt"]

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "user":
            createdMessageValue = await cosmos_conversation_client.create_message(
                uuid=str(uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
            if createdMessageValue == "Conversation not found":
                return func.HttpResponse(
                    json.dumps({"error": f"Conversation not found"}), status_code=400
                )
        else:
            return func.HttpResponse(
                json.dumps({"error": f"User not found"}), status_code=400
            )

        # # Submit request to Chat Completions for response
        # request_body = await request.get_json()
        # history_metadata["conversation_id"] = conversation_id
        # request_body["history_metadata"] = history_metadata
        # return await conversation_internal(request_body, request.headers)

    except Exception as e:
        logger.exception("Exception in /history/generate")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route("/history/update", methods=[func.HttpMethod.POST])
async def update_conversation(request: func.HttpRequest) -> func.HttpResponse:
    if not CHAT_HISTORY_ENABLED:
        return func.HttpResponse(
            json.dumps({"error": f"Chat history is not avaliable"}), status_code=400
        )

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            return func.HttpResponse(
                json.dumps({"error": "database not available"}), status_code=500
            )

        # check for the conversation_id, if the conversation is not set, we will create a new one
        if not conversation_id:
            return func.HttpResponse(
                json.dumps({"error": "conversation_id is required"}), status_code=400
            )

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
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
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            return func.HttpResponse(
                json.dumps({"error": "no conversationbot"}), status_code=400
            )

        # Submit request to Chat Completions for response

        return func.HttpResponse(json.dumps({"success": True}), 200)

    except Exception as e:
        logger.exception("Exception in /history/update")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)


@bp_chat_history_response.route(
    "/history/frontend_settings", methods=[func.HttpMethod.GET]
)
def get_frontend_settings():
    try:
        return func.HttpResponse(
            json.dumps({"CHAT_HISTORY_ENABLED": CHAT_HISTORY_ENABLED}), 200
        )
    except Exception as e:
        logger.exception("Exception in /history/frontend_settings")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)
