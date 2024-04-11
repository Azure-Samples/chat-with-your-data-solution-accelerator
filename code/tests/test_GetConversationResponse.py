import sys
import os
from unittest.mock import patch, Mock, ANY
import json

function_app_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../backend/batch")
)
sys.path.append(function_app_path)

from backend.batch.GetConversationResponse import (  # noqa: E402
    do_get_conversation_response,
)


@patch("backend.batch.BatchPushResults.ConfigHelper")
@patch("backend.batch.GetConversationResponse.Orchestrator")
def test_get_conversation_response(mock_create_message_orchestrator, _):
    mock_http_request = Mock()
    request_json = {
        "messages": [
            {"content": "Do I have meetings today?", "role": "user"},
            {"content": "It is sunny today", "role": "assistant"},
            {"content": "What is the weather like today?", "role": "user"},
        ],
        "conversation_id": "13245",
    }
    mock_http_request.get_json.return_value = request_json

    mock_message_orchestrator = Mock()
    mock_message_orchestrator.handle_message.return_value = [
        "You don't have any meetings today"
    ]

    mock_create_message_orchestrator.return_value = mock_message_orchestrator

    response = do_get_conversation_response(mock_http_request)

    assert response.status_code == 200

    mock_message_orchestrator.handle_message.assert_called_once_with(
        user_message="What is the weather like today?",
        chat_history=[("Do I have meetings today?", "It is sunny today")],
        conversation_id="13245",
        orchestrator=ANY,
    )

    response_json = json.loads(response.get_body())
    assert response_json["id"] == "response.id"
    assert response_json["choices"] == [
        {"messages": ["You don't have any meetings today"]}
    ]
