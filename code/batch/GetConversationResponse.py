import azure.functions as func
import logging
import json
import os
import sys
from utilities.helpers.OrchestratorHelper import Orchestrator

sys.path.append("..")

bp_get_conversation_response = func.Blueprint()

@bp_get_conversation_response.route(route="GetConversationResponse")
def get_conversation_response(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")


    message_orchestrator = Orchestrator()

    try:
        req_body = req.get_json()
        user_message = req_body["messages"][-1]["content"]
        conversation_id = req_body["conversation_id"]
        user_assistant_messages = list(
            filter(
                lambda x: x["role"] in ("user", "assistant"), req_body["messages"][0:-1]
            )
        )
        chat_history = []
        for i, k in enumerate(user_assistant_messages):
            if i % 2 == 0:
                chat_history.append(
                    (
                        user_assistant_messages[i]["content"],
                        user_assistant_messages[i + 1]["content"],
                    )
                )
        from utilities.helpers.ConfigHelper import ConfigHelper

        messages = message_orchestrator.handle_message(
            user_message=user_message,
            chat_history=chat_history,
            conversation_id=conversation_id,
            orchestrator=ConfigHelper.get_active_config_or_default().orchestrator,
        )

        response_obj = {
            "id": "response.id",
            "model": os.getenv("AZURE_OPENAI_MODEL"),
            "created": "response.created",
            "object": "response.object",
            "choices": [{"messages": messages}],
        }

        return func.HttpResponse(json.dumps(response_obj), status_code=200)

    except Exception as e:
        logging.exception("Exception in /api/GetConversationResponse")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)