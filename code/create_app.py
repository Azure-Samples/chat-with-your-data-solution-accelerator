import json
import logging
from os import path
import requests
from openai import AzureOpenAI
import mimetypes
from flask import Flask, Response, request, jsonify
from dotenv import load_dotenv
import sys
import functools
from backend.batch.utilities.helpers.EnvHelper import EnvHelper
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


def prepare_body_headers_with_data(request, env_helper: EnvHelper):
    request_messages = request.json["messages"]

    body = {
        "messages": request_messages,
        "temperature": float(env_helper.AZURE_OPENAI_TEMPERATURE),
        "max_tokens": int(env_helper.AZURE_OPENAI_MAX_TOKENS),
        "top_p": float(env_helper.AZURE_OPENAI_TOP_P),
        "stop": (
            env_helper.AZURE_OPENAI_STOP_SEQUENCE.split("|")
            if env_helper.AZURE_OPENAI_STOP_SEQUENCE
            else None
        ),
        "stream": env_helper.SHOULD_STREAM,
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    # authentication is set below
                    "endpoint": env_helper.AZURE_SEARCH_SERVICE,
                    "index_name": env_helper.AZURE_SEARCH_INDEX,
                    "fields_mapping": {
                        "content_fields": (
                            env_helper.AZURE_SEARCH_CONTENT_COLUMNS.split("|")
                            if env_helper.AZURE_SEARCH_CONTENT_COLUMNS
                            else []
                        ),
                        "title_field": env_helper.AZURE_SEARCH_TITLE_COLUMN or None,
                        "url_field": env_helper.AZURE_SEARCH_URL_COLUMN or None,
                        "filepath_field": (
                            env_helper.AZURE_SEARCH_FILENAME_COLUMN or None
                        ),
                    },
                    "filter": env_helper.AZURE_SEARCH_FILTER,
                    "in_scope": env_helper.AZURE_SEARCH_ENABLE_IN_DOMAIN,
                    "top_n_documents": env_helper.AZURE_SEARCH_TOP_K,
                    "query_type": (
                        "semantic"
                        if env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH
                        else "simple"
                    ),
                    "semantic_configuration": (
                        env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
                        if env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH
                        and env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG
                        else ""
                    ),
                    "role_information": env_helper.AZURE_OPENAI_SYSTEM_MESSAGE,
                },
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "x-ms-useragent": "GitHubSampleWebApp/PublicAPI/1.0.0",
    }

    if env_helper.AZURE_AUTH_TYPE == "rbac":
        body["data_sources"][0]["parameters"]["authentication"] = {
            "type": "system_assigned_managed_identity"
        }
        headers["Authorization"] = f"Bearer {env_helper.AZURE_TOKEN_PROVIDER()}"
    else:
        body["data_sources"][0]["parameters"]["authentication"] = {
            "type": "api_key",
            "key": env_helper.AZURE_SEARCH_KEY,
        }
        headers["api-key"] = env_helper.AZURE_OPENAI_API_KEY

    return body, headers


def stream_with_data(body, headers, endpoint):
    s = requests.Session()
    response = {
        "id": "",
        "model": "",
        "created": 0,
        "object": "",
        "choices": [
            {
                "messages": [
                    {
                        "content": "",
                        "end_turn": False,
                        "role": "tool",
                    },
                    {
                        "content": "",
                        "end_turn": False,
                        "role": "assistant",
                    },
                ]
            }
        ],
    }
    try:
        with s.post(endpoint, json=body, headers=headers, stream=True) as r:
            for line in r.iter_lines(chunk_size=10):
                if line:
                    lineJson = json.loads(line.lstrip(b"data: ").decode("utf-8"))
                    if "error" in lineJson:
                        yield json.dumps(lineJson, ensure_ascii=False) + "\n"
                        return

                    if lineJson["choices"][0]["end_turn"]:
                        response["choices"][0]["messages"][1]["end_turn"] = True
                        yield json.dumps(response, ensure_ascii=False) + "\n"
                        return

                    response["id"] = lineJson["id"]
                    response["model"] = lineJson["model"]
                    response["created"] = lineJson["created"]
                    response["object"] = lineJson["object"]

                    delta = lineJson["choices"][0]["delta"]
                    role = delta.get("role")

                    if role == "assistant":
                        response["choices"][0]["messages"][0]["content"] = json.dumps(
                            delta["context"],
                            ensure_ascii=False,
                        )
                    else:
                        response["choices"][0]["messages"][1]["content"] += delta[
                            "content"
                        ]

                    yield json.dumps(response, ensure_ascii=False) + "\n"
    except Exception as e:
        yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"


def conversation_with_data(request, env_helper: EnvHelper):
    body, headers = prepare_body_headers_with_data(request, env_helper)
    endpoint = f"{env_helper.AZURE_OPENAI_ENDPOINT}openai/deployments/{env_helper.AZURE_OPENAI_MODEL}/chat/completions?api-version={env_helper.AZURE_OPENAI_API_VERSION}"

    if not env_helper.SHOULD_STREAM:
        r = requests.post(endpoint, headers=headers, json=body)
        status_code = r.status_code
        r = r.json()

        response = {
            "id": r["id"],
            "model": r["model"],
            "created": r["created"],
            "object": r["object"],
            "choices": [
                {
                    "messages": [
                        {
                            "content": json.dumps(
                                r["choices"][0]["message"]["context"],
                                ensure_ascii=False,
                            ),
                            "end_turn": False,
                            "role": "tool",
                        },
                        {
                            "content": r["choices"][0]["message"]["content"],
                            "end_turn": True,
                            "role": "assistant",
                        },
                    ]
                }
            ],
        }

        return jsonify(response), status_code
    else:
        return Response(
            stream_with_data(body, headers, endpoint),
            mimetype="application/json-lines",
        )


def stream_without_data(response):
    responseText = ""
    for line in response:
        if not line.choices:
            continue

        deltaText = line.choices[0].delta.content

        if deltaText is None:
            return

        responseText += deltaText

        response_obj = {
            "id": line.id,
            "model": line.model,
            "created": line.created,
            "object": line.object,
            "choices": [{"messages": [{"role": "assistant", "content": responseText}]}],
        }
        yield json.dumps(response_obj, ensure_ascii=False) + "\n"


def get_message_orchestrator():
    from backend.batch.utilities.helpers.OrchestratorHelper import Orchestrator

    return Orchestrator()


def get_orchestrator_config():
    from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper

    return ConfigHelper.get_active_config_or_default().orchestrator


def conversation_without_data(request, env_helper):
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
            "id": response.id,
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
        return Response(
            stream_without_data(response), mimetype="application/json-lines"
        )


@functools.cache
def get_speech_key(env_helper: EnvHelper):
    """
    Get the Azure Speech key directly from Azure.
    This is required to generate short-lived tokens when using RBAC.
    """
    client = CognitiveServicesManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=env_helper.AZURE_SUBSCRIPTION_ID,
    )
    keys = client.accounts.list_keys(
        resource_group_name=env_helper.AZURE_RESOURCE_GROUP,
        account_name=env_helper.AZURE_SPEECH_SERVICE_NAME,
    )

    return keys.key1


def create_app():
    # Fixing MIME types for static files under Windows
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")

    sys.path.append(path.join(path.dirname(__file__), ".."))

    load_dotenv(
        path.join(path.dirname(__file__), "..", "..", ".env")
    )  # Load environment variables from .env file

    app = Flask(__name__)
    env_helper: EnvHelper = EnvHelper()

    logger.debug("Starting web app")

    @app.route("/", defaults={"path": "index.html"})
    @app.route("/<path:path>")
    def static_file(path):
        return app.send_static_file(path)

    @app.route("/api/health", methods=["GET"])
    def health():
        return "OK"

    @app.route("/api/conversation/azure_byod", methods=["POST"])
    def conversation_azure_byod():
        try:
            if env_helper.should_use_data():
                return conversation_with_data(request, env_helper)
            else:
                return conversation_without_data(request, env_helper)
        except Exception as e:
            errorMessage = str(e)
            logger.exception(
                f"Exception in /api/conversation/azure_byod | {errorMessage}"
            )
            return (
                jsonify(
                    {
                        "error": "Exception in /api/conversation/azure_byod. See log for more details."
                    }
                ),
                500,
            )

    @app.route("/api/conversation/custom", methods=["POST"])
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
            logger.exception(f"Exception in /api/conversation/custom | {errorMessage}")
            return (
                jsonify(
                    {
                        "error": "Exception in /api/conversation/custom. See log for more details."
                    }
                ),
                500,
            )

    @app.route("/api/speech", methods=["GET"])
    def speech_config():
        try:
            speech_key = env_helper.AZURE_SPEECH_KEY or get_speech_key(env_helper)

            response = requests.post(
                f"{env_helper.AZURE_SPEECH_REGION_ENDPOINT}sts/v1.0/issueToken",
                headers={
                    "Ocp-Apim-Subscription-Key": speech_key,
                },
            )

            if response.status_code == 200:
                return {
                    "token": response.text,
                    "region": env_helper.AZURE_SPEECH_SERVICE_REGION,
                    "languages": env_helper.SPEECH_RECOGNIZER_LANGUAGES,
                }

            logger.error(f"Failed to get speech config: {response.text}")
            return {"error": "Failed to get speech config"}, response.status_code
        except Exception as e:
            logger.exception(f"Exception in /api/speech | {str(e)}")

            return {"error": "Failed to get speech config"}, 500

    return app
