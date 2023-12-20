import sys
from dotenv import load_dotenv
from flask import Flask, Response, request, jsonify
import json
import os
import logging
import requests
import openai

# Fixing MIME types for static files under Windows
import mimetypes

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

app = Flask(__name__)


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_file(path):
    return app.send_static_file(path)


@app.route('/api/config', methods=['GET'])
def get_config():
    """
    Retrieves the environment variables or other configuration data and returns it as JSON.

    Returns:
        dict: A dictionary containing the configuration data with keys 'azureSpeechKey' and 'azureSpeechRegion'.
    """
    azure_speech_key = os.getenv('AZURE_SPEECH_SERVICE_KEY')
    azure_speech_region = os.getenv('AZURE_SPEECH_SERVICE_REGION')

    return jsonify({
        'azureSpeechKey': azure_speech_key,
        'azureSpeechRegion': azure_speech_region
    })


# ACS Integration Settings
AZURE_SEARCH_SERVICE = os.environ.get("AZURE_SEARCH_SERVICE")
AZURE_SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX")
AZURE_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY")
AZURE_SEARCH_USE_SEMANTIC_SEARCH = os.environ.get(
    "AZURE_SEARCH_USE_SEMANTIC_SEARCH", False)
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = os.environ.get(
    "AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", "default")
AZURE_SEARCH_TOP_K = os.environ.get("AZURE_SEARCH_TOP_K", 5)
AZURE_SEARCH_ENABLE_IN_DOMAIN = os.environ.get(
    "AZURE_SEARCH_ENABLE_IN_DOMAIN", "true")
AZURE_SEARCH_CONTENT_COLUMNS = os.environ.get("AZURE_SEARCH_CONTENT_COLUMNS")
AZURE_SEARCH_FILENAME_COLUMN = os.environ.get("AZURE_SEARCH_FILENAME_COLUMN")
AZURE_SEARCH_TITLE_COLUMN = os.environ.get("AZURE_SEARCH_TITLE_COLUMN")
AZURE_SEARCH_URL_COLUMN = os.environ.get("AZURE_SEARCH_URL_COLUMN")

# AOAI Integration Settings
AZURE_OPENAI_RESOURCE = os.environ.get("AZURE_OPENAI_RESOURCE")
AZURE_OPENAI_MODEL = os.environ.get("AZURE_OPENAI_MODEL")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
AZURE_OPENAI_TEMPERATURE = os.environ.get("AZURE_OPENAI_TEMPERATURE", 0)
AZURE_OPENAI_TOP_P = os.environ.get("AZURE_OPENAI_TOP_P", 1.0)
AZURE_OPENAI_MAX_TOKENS = os.environ.get("AZURE_OPENAI_MAX_TOKENS", 1000)
AZURE_OPENAI_STOP_SEQUENCE = os.environ.get("AZURE_OPENAI_STOP_SEQUENCE")
AZURE_OPENAI_SYSTEM_MESSAGE = os.environ.get(
    "AZURE_OPENAI_SYSTEM_MESSAGE", "You are an AI assistant that helps people find information.")
AZURE_OPENAI_API_VERSION = os.environ.get(
    "AZURE_OPENAI_API_VERSION", "2023-06-01-preview")
AZURE_OPENAI_STREAM = os.environ.get("AZURE_OPENAI_STREAM", "true")
# Name of the model, e.g. 'gpt-35-turbo' or 'gpt-4'
AZURE_OPENAI_MODEL_NAME = os.environ.get(
    "AZURE_OPENAI_MODEL_NAME", "gpt-35-turbo")

SHOULD_STREAM = True if AZURE_OPENAI_STREAM.lower() == "true" else False


def is_chat_model():
    """
    Checks if the current model is a chat model.

    Returns:
        bool: True if the model is a chat model, False otherwise.
    """
    if 'gpt-4' in AZURE_OPENAI_MODEL_NAME.lower():
        return True
    return False


def should_use_data():
    """
    Determines whether data should be used based on the presence of Azure Search service, index, and key.

    Returns:
        bool: True if data should be used, False otherwise.
    """
    if AZURE_SEARCH_SERVICE and AZURE_SEARCH_INDEX and AZURE_SEARCH_KEY:
        return True
    return False


def prepare_body_headers_with_data(request):
    """
    Prepares the body and headers for the API request.

    Args:
        request (dict): The request object containing the messages.

    Returns:
        tuple: A tuple containing the body and headers for the API request.
    """
    request_messages = request.json["messages"]

    body = {
        "messages": request_messages,
        "temperature": AZURE_OPENAI_TEMPERATURE,
        "max_tokens": AZURE_OPENAI_MAX_TOKENS,
        "top_p": AZURE_OPENAI_TOP_P,
        "stop": AZURE_OPENAI_STOP_SEQUENCE.split("|") if AZURE_OPENAI_STOP_SEQUENCE else [],
        "stream": SHOULD_STREAM,
        "dataSources": [
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": f"https://{AZURE_SEARCH_SERVICE}.search.windows.net",
                    "key": AZURE_SEARCH_KEY,
                    "indexName": AZURE_SEARCH_INDEX,
                    "fieldsMapping": {
                        "contentField": AZURE_SEARCH_CONTENT_COLUMNS.split("|") if AZURE_SEARCH_CONTENT_COLUMNS else [],
                        "titleField": AZURE_SEARCH_TITLE_COLUMN if AZURE_SEARCH_TITLE_COLUMN else None,
                        "urlField": AZURE_SEARCH_URL_COLUMN if AZURE_SEARCH_URL_COLUMN else None,
                        "filepathField": AZURE_SEARCH_FILENAME_COLUMN if AZURE_SEARCH_FILENAME_COLUMN else None
                    },
                    "inScope": True if AZURE_SEARCH_ENABLE_IN_DOMAIN.lower() == "true" else False,
                    "topNDocuments": AZURE_SEARCH_TOP_K,
                    "queryType": "semantic" if AZURE_SEARCH_USE_SEMANTIC_SEARCH.lower() == "true" else "simple",
                    "semanticConfiguration": AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG if AZURE_SEARCH_USE_SEMANTIC_SEARCH.lower() == "true" and AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG else "",
                    "roleInformation": AZURE_OPENAI_SYSTEM_MESSAGE
                }
            }
        ]
    }

    chatgpt_url = f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/openai/deployments/{AZURE_OPENAI_MODEL}"
    if is_chat_model():
        chatgpt_url += "/chat/completions?api-version=2023-03-15-preview"
    else:
        chatgpt_url += "/completions?api-version=2023-03-15-preview"

    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_OPENAI_KEY,
        'chatgpt_url': chatgpt_url,
        'chatgpt_key': AZURE_OPENAI_KEY,
        "x-ms-useragent": "GitHubSampleWebApp/PublicAPI/1.0.0"
    }

    return body, headers


def stream_with_data(body, headers, endpoint):
    """
    Stream data using a POST request to the specified endpoint.

    Args:
        body (dict): The request body as a JSON object.
        headers (dict): The request headers.
        endpoint (str): The URL endpoint to send the request to.

    Yields:
        str: JSON-encoded response for each line received from the server.

    Returns:
        None
    """
    s = requests.Session()
    response = {
        "id": "",
        "model": "",
        "created": 0,
        "object": "",
        "choices": [{
            "messages": []
        }]
    }
    try:
        with s.post(endpoint, json=body, headers=headers, stream=True) as r:
            for line in r.iter_lines(chunk_size=10):
                if line:
                    line_json = json.loads(
                        line.lstrip(b'data:').decode('utf-8'))
                    if 'error' in line_json:
                        yield json.dumps(line_json).replace("\n", "\\n") + "\n"
                    response["id"] = line_json["id"]
                    response["model"] = line_json["model"]
                    response["created"] = line_json["created"]
                    response["object"] = line_json["object"]

                    role = line_json["choices"][0]["messages"][0]["delta"].get(
                        "role")
                    if role == "tool":
                        response["choices"][0]["messages"].append(
                            line_json["choices"][0]["messages"][0]["delta"])
                    elif role == "assistant":
                        response["choices"][0]["messages"].append({
                            "role": "assistant",
                            "content": ""
                        })
                    else:
                        deltaText = line_json["choices"][0]["messages"][0]["delta"]["content"]
                        if deltaText != "[DONE]":
                            response["choices"][0]["messages"][1]["content"] += deltaText

                    yield json.dumps(response).replace("\n", "\\n") + "\n"
    except Exception as e:
        yield json.dumps({"error": str(e)}).replace("\n", "\\n") + "\n"


def conversation_with_data(request):
    """
    Perform a conversation with data using the Azure OpenAI API.

    Args:
        request: The HTTP request object.

    Returns:
        If SHOULD_STREAM is False, returns a JSON response containing the result of the conversation.
        If SHOULD_STREAM is True and the request method is POST, returns a text/event-stream response with streamed data.
        If SHOULD_STREAM is True and the request method is not POST, returns a text/event-stream response with no data.
    """
    body, headers = prepare_body_headers_with_data(request)
    endpoint = f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/openai/deployments/{AZURE_OPENAI_MODEL}/extensions/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

    if not SHOULD_STREAM:
        r = requests.post(endpoint, headers=headers, json=body)
        status_code = r.status_code
        r = r.json()

        return Response(json.dumps(r).replace("\n", "\\n"), status=status_code)
    else:
        if request.method == "POST":
            return Response(stream_with_data(body, headers, endpoint), mimetype='text/event-stream')
        else:
            return Response(None, mimetype='text/event-stream')


def stream_without_data(response):
    """
    Stream the response data without including the data itself.

    Args:
        response (iterable): An iterable containing the response data.

    Yields:
        str: A JSON string representation of the response object, excluding the data.

    """
    responseText = ""
    for line in response:
        deltaText = line["choices"][0]["delta"].get('content')
        if deltaText and deltaText != "[DONE]":
            responseText += deltaText

        response_obj = {
            "id": line["id"],
            "model": line["model"],
            "created": line["created"],
            "object": line["object"],
            "choices": [{
                "messages": [{
                    "role": "assistant",
                    "content": responseText
                }]
            }]
        }
        yield json.dumps(response_obj).replace("\n", "\\n") + "\n"


def conversation_without_data(request):
    """
    Perform a conversation without using any data.

    Args:
        request (object): The request object containing the messages.

    Returns:
        object: The response object containing the generated message.

    Raises:
        None
    """
    openai.api_type = "azure"
    openai.api_base = f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/"
    openai.api_version = "2023-03-15-preview"
    openai.api_key = AZURE_OPENAI_KEY

    request_messages = request.json["messages"]
    messages = [
        {
            "role": "system",
            "content": AZURE_OPENAI_SYSTEM_MESSAGE
        }
    ]

    for message in request_messages:
        messages.append({
            "role": message["role"],
            "content": message["content"]
        })

    response = openai.ChatCompletion.create(
        engine=AZURE_OPENAI_MODEL,
        messages=messages,
        temperature=float(AZURE_OPENAI_TEMPERATURE),
        max_tokens=int(AZURE_OPENAI_MAX_TOKENS),
        top_p=float(AZURE_OPENAI_TOP_P),
        stop=AZURE_OPENAI_STOP_SEQUENCE.split(
            "|") if AZURE_OPENAI_STOP_SEQUENCE else None,
        stream=SHOULD_STREAM
    )

    if not SHOULD_STREAM:
        response_obj = {
            "id": response,
            "model": response.model,
            "created": response.created,
            "object": response.object,
            "choices": [{
                "messages": [{
                    "role": "assistant",
                    "content": response.choices[0].message.content
                }]
            }]
        }

        return jsonify(response_obj), 200
    else:
        if request.method == "POST":
            return Response(stream_without_data(response), mimetype='text/event-stream')
        else:
            return Response(None, mimetype='text/event-stream')


@app.route("/api/conversation/azure_byod", methods=["GET", "POST"])
def conversation_azure_byod():
    """
    Handles the conversation flow for Azure BYOD (Bring Your Own Data) scenario.

    This function checks if data should be used and calls the appropriate conversation function accordingly.
    If an exception occurs, it logs the error and returns an error response.

    Returns:
        A JSON response containing the conversation result or an error message.
    """
    try:
        use_data = should_use_data()
        if use_data:
            return conversation_with_data(request)
        else:
            return conversation_without_data(request)
    except Exception as e:
        errorMessage = str(e)
        logging.exception(
            f"Exception in /api/conversation/azure_byod | {errorMessage}")
        return jsonify({"error": "Exception in /api/conversation/azure_byod. See log for more details."}), 500


@app.route("/api/conversation/custom", methods=["GET", "POST"])
def conversation_custom():
    """
    Handles a custom conversation by processing the user message and generating a response.

    Returns:
        A JSON response containing the generated message and other metadata.
    """
    from utilities.helpers.OrchestratorHelper import Orchestrator, OrchestrationSettings
    message_orchestrator = Orchestrator()

    try:
        user_message = request.json["messages"][-1]['content']
        conversation_id = request.json["conversation_id"]
        user_assistant_messages = list(filter(lambda x: x['role'] in (
            'user', 'assistant'), request.json["messages"][0:-1]))
        chat_history = []
        for i, k in enumerate(user_assistant_messages):
            if i % 2 == 0:
                chat_history.append(
                    (user_assistant_messages[i]['content'], user_assistant_messages[i+1]['content']))
        from utilities.helpers.ConfigHelper import ConfigHelper
        messages = message_orchestrator.handle_message(user_message=user_message, chat_history=chat_history,
                                                       conversation_id=conversation_id, orchestrator=ConfigHelper.get_active_config_or_default().orchestrator)

        response_obj = {
            "id": "response.id",
            "model": os.getenv("AZURE_OPENAI_MODEL"),
            "created": "response.created",
            "object": "response.object",
            "choices": [{
                "messages": messages
            }]
        }

        return jsonify(response_obj), 200

    except Exception as e:
        errorMessage = str(e)
        logging.exception(
            f"Exception in /api/conversation/custom | {errorMessage}")
        return jsonify({"error": "Exception in /api/conversation/custom. See log for more details."}), 500


if __name__ == "__main__":
    app.run()
