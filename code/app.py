import json
import logging
from os import path
import requests
from openai import AzureOpenAI
import mimetypes
from flask import Flask, Response, request, jsonify
from dotenv import load_dotenv
import sys
from backend.batch.utilities.helpers.EnvHelper import EnvHelper
from azure.monitor.opentelemetry import configure_azure_monitor

# Fixing MIME types for static files under Windows
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

sys.path.append(path.join(path.dirname(__file__), ".."))

load_dotenv(
    path.join(path.dirname(__file__), "..", "..", ".env")
)  # Load environment variables from .env file

app = Flask(__name__)
env_helper: EnvHelper = EnvHelper()


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_file(path):
    return app.send_static_file(path)


@app.route("/api/config", methods=["GET"])
def get_config():
    # Return the configuration data as JSON
    return jsonify(
        {
            "azureSpeechKey": env_helper.AZURE_SPEECH_KEY,
            "azureSpeechRegion": env_helper.AZURE_SPEECH_SERVICE_REGION,
            "AZURE_OPENAI_ENDPOINT": env_helper.AZURE_OPENAI_ENDPOINT,
        }
    )


def prepare_body_headers_with_data(request):
    request_messages = request.json["messages"]

    body = {
        "messages": request_messages,
        "temperature": env_helper.AZURE_OPENAI_TEMPERATURE,
        "max_tokens": env_helper.AZURE_OPENAI_MAX_TOKENS,
        "top_p": env_helper.AZURE_OPENAI_TOP_P,
        "stop": (
            env_helper.AZURE_OPENAI_STOP_SEQUENCE.split("|")
            if env_helper.AZURE_OPENAI_STOP_SEQUENCE
            else None
        ),
        "stream": env_helper.SHOULD_STREAM,
        "dataSources": [
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": env_helper.AZURE_SEARCH_SERVICE,
                    "key": env_helper.AZURE_SEARCH_KEY,
                    "indexName": env_helper.AZURE_SEARCH_INDEX,
                    "fieldsMapping": {
                        "contentField": (
                            env_helper.AZURE_SEARCH_CONTENT_COLUMNS.split("|")
                            if env_helper.AZURE_SEARCH_CONTENT_COLUMNS
                            else []
                        ),
                        "titleField": (
                            env_helper.AZURE_SEARCH_TITLE_COLUMN
                            if env_helper.AZURE_SEARCH_TITLE_COLUMN
                            else None
                        ),
                        "urlField": (
                            env_helper.AZURE_SEARCH_URL_COLUMN
                            if env_helper.AZURE_SEARCH_URL_COLUMN
                            else None
                        ),
                        "filepathField": (
                            env_helper.AZURE_SEARCH_FILENAME_COLUMN
                            if env_helper.AZURE_SEARCH_FILENAME_COLUMN
                            else None
                        ),
                    },
                    "inScope": env_helper.AZURE_SEARCH_ENABLE_IN_DOMAIN,
                    "topNDocuments": env_helper.AZURE_SEARCH_TOP_K,
                    "queryType": (
                        "semantic"
                        if env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH
                        else "simple"
                    ),
                    "semanticConfiguration": (
                        env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
                        if env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH
                        and env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
                        else ""
                    ),
                    "roleInformation": env_helper.AZURE_OPENAI_SYSTEM_MESSAGE,
                },
            }
        ],
    }

    chatgpt_url = f"{env_helper.AZURE_OPENAI_ENDPOINT}openai/deployments/{env_helper.AZURE_OPENAI_MODEL}"
    if env_helper.is_chat_model():
        chatgpt_url += "/chat/completions?api-version=2023-12-01-preview"
    else:
        chatgpt_url += "/completions?api-version=2023-12-01-preview"

    headers = {
        "Content-Type": "application/json",
        "api-key": env_helper.AZURE_OPENAI_API_KEY,
        "chatgpt_url": chatgpt_url,
        "chatgpt_key": env_helper.AZURE_OPENAI_API_KEY,
        "x-ms-useragent": "GitHubSampleWebApp/PublicAPI/1.0.0",
    }

    return body, headers


def stream_with_data(body, headers, endpoint):
    s = requests.Session()
    response = {
        "id": "",
        "model": "",
        "created": 0,
        "object": "",
        "choices": [{"messages": []}],
    }
    try:
        with s.post(endpoint, json=body, headers=headers, stream=True) as r:
            for line in r.iter_lines(chunk_size=10):
                if line:
                    lineJson = json.loads(line.lstrip(b"data:").decode("utf-8"))
                    if "error" in lineJson:
                        yield json.dumps(lineJson, ensure_ascii=False) + "\n"
                    response["id"] = lineJson["id"]
                    response["model"] = lineJson["model"]
                    response["created"] = lineJson["created"]
                    response["object"] = lineJson["object"]

                    role = lineJson["choices"][0]["messages"][0]["delta"].get("role")
                    if role == "tool":
                        response["choices"][0]["messages"].append(
                            lineJson["choices"][0]["messages"][0]["delta"]
                        )
                    elif role == "assistant":
                        response["choices"][0]["messages"].append(
                            {"role": "assistant", "content": ""}
                        )
                    else:
                        deltaText = lineJson["choices"][0]["messages"][0]["delta"][
                            "content"
                        ]
                        if deltaText != "[DONE]":
                            response["choices"][0]["messages"][1][
                                "content"
                            ] += deltaText

                    yield json.dumps(response, ensure_ascii=False) + "\n"
    except Exception as e:
        yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"


def conversation_with_data(request):
    body, headers = prepare_body_headers_with_data(request)
    endpoint = f"{env_helper.AZURE_OPENAI_ENDPOINT}openai/deployments/{env_helper.AZURE_OPENAI_MODEL}/extensions/chat/completions?api-version={env_helper.AZURE_OPENAI_API_VERSION}"

    if not env_helper.SHOULD_STREAM:
        r = requests.post(endpoint, headers=headers, json=body)
        status_code = r.status_code
        r = r.json()

        return Response(json.dumps(r, ensure_ascii=False), status=status_code)
    else:
        if request.method == "POST":
            return Response(
                stream_with_data(body, headers, endpoint),
                mimetype="application/json-lines",
            )
        else:
            return Response(None, mimetype="application/json-lines")


def stream_without_data(response):
    responseText = ""
    for line in response:
        deltaText = line["choices"][0]["delta"].get("content")
        if deltaText and deltaText != "[DONE]":
            responseText += deltaText

        response_obj = {
            "id": line["id"],
            "model": line["model"],
            "created": line["created"],
            "object": line["object"],
            "choices": [{"messages": [{"role": "assistant", "content": responseText}]}],
        }
        yield json.dumps(response_obj).replace("\n", "\\n") + "\n"


def conversation_without_data(request):
    if env_helper.AZURE_AUTH_TYPE == "rbac":
        openai_client = AzureOpenAI(
            azure_endpoint=env_helper.AZURE_OPENAI_ENDPOINT,
            api_version=env_helper.AZURE_OPENAI_API_VERSION,
            azure_ad_token_provider=env_helper.AZURE_TOKEN_PROVIDER,
        )
    else:
        openai_client = AzureOpenAI(
            azure_endpoint=env_helper.AZURE_OPENAI_ENDPOINT,
            api_version=env_helper.AZURE_OPENAI_API_VERSION,
            api_key=env_helper.AZURE_OPENAI_API_KEY,
        )

    request_messages = request.json["messages"]
    messages = [{"role": "system", "content": env_helper.AZURE_OPENAI_SYSTEM_MESSAGE}]

    for message in request_messages:
        messages.append({"role": message["role"], "content": message["content"]})

    # Azure Open AI takes the deployment name as the model name, "AZURE_OPENAI_MODEL" means deployment name.
    response = openai_client.chat.completions.create(
        model=env_helper.AZURE_OPENAI_MODEL,
        messages=messages,
        temperature=float(env_helper.AZURE_OPENAI_TEMPERATURE),
        max_tokens=int(env_helper.AZURE_OPENAI_MAX_TOKENS),
        top_p=float(env_helper.AZURE_OPENAI_TOP_P),
        stop=(
            env_helper.AZURE_OPENAI_STOP_SEQUENCE.split("|")
            if env_helper.AZURE_OPENAI_STOP_SEQUENCE
            else None
        ),
        stream=env_helper.SHOULD_STREAM,
    )

    if not env_helper.SHOULD_STREAM:
        response_obj = {
            "id": response,
            "model": response.model,
            "created": response.created,
            "object": response.object,
            "choices": [
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    ]
                }
            ],
        }

        return jsonify(response_obj), 200
    else:
        if request.method == "POST":
            return Response(
                stream_without_data(response), mimetype="application/json-lines"
            )
        else:
            return Response(None, mimetype="application/json-lines")


@app.route("/api/conversation/azure_byod", methods=["GET", "POST"])
def conversation_azure_byod():
    try:
        if env_helper.should_use_data():
            return conversation_with_data(request)
        else:
            return conversation_without_data(request)
    except Exception as e:
        errorMessage = str(e)
        logging.exception(f"Exception in /api/conversation/azure_byod | {errorMessage}")
        return (
            jsonify(
                {
                    "error": "Exception in /api/conversation/azure_byod. See log for more details."
                }
            ),
            500,
        )


def get_message_orchestrator():
    from backend.batch.utilities.helpers.OrchestratorHelper import Orchestrator

    return Orchestrator()


def get_orchestrator_config():
    from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper

    return ConfigHelper.get_active_config_or_default().orchestrator


@app.route("/api/conversation/custom", methods=["GET", "POST"])
def conversation_custom():
    message_orchestrator = get_message_orchestrator()

    try:
        user_message = request.json["messages"][-1]["content"]
        conversation_id = request.json["conversation_id"]
        user_assistant_messages = list(
            filter(
                lambda x: x["role"] in ("user", "assistant"),
                request.json["messages"][0:-1],
            )
        )

        messages = message_orchestrator.handle_message(
            user_message=user_message,
            chat_history=user_assistant_messages,
            conversation_id=conversation_id,
            orchestrator=get_orchestrator_config(),
        )

        response_obj = {
            "id": "response.id",
            "model": env_helper.AZURE_OPENAI_MODEL,
            "created": "response.created",
            "object": "response.object",
            "choices": [{"messages": messages}],
        }

        return jsonify(response_obj), 200

    except Exception as e:
        errorMessage = str(e)
        logging.exception(f"Exception in /api/conversation/custom | {errorMessage}")
        return (
            jsonify(
                {
                    "error": "Exception in /api/conversation/custom. See log for more details."
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run()
    configure_azure_monitor()
