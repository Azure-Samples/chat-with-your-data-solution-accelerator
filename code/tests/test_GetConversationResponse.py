import sys
import os
from unittest.mock import AsyncMock, patch, Mock, ANY
import pytest
import json

sys.path.append(os.path.join(os.path.dirname(sys.path[0]), "backend", "batch"))

from backend.batch.GetConversationResponse import (  # noqa: E402
    get_conversation_response,
)


@patch("backend.batch.GetConversationResponse.ConfigHelper")
@patch("backend.batch.GetConversationResponse.Orchestrator")
@pytest.mark.asyncio
async def test_get_conversation_response(mock_create_message_orchestrator, _):
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

    mock_message_orchestrator = AsyncMock()
    mock_message_orchestrator.handle_message.return_value = [
        "You don't have any meetings today"
    ]

    mock_create_message_orchestrator.return_value = mock_message_orchestrator

    response = await get_conversation_response.build().get_user_function()(
        mock_http_request
    )

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


@patch("backend.batch.GetConversationResponse.ConfigHelper")
@patch("backend.batch.GetConversationResponse.Orchestrator")
@pytest.mark.asyncio
async def test_get_conversation_error(_, __):
    mock_http_request = Mock()
    mock_http_request.get_json.side_effect = Exception("Error")

    response = await get_conversation_response.build().get_user_function()(
        mock_http_request
    )

    assert response.status_code == 500

    response_json = json.loads(response.get_body())
    assert response_json == {"error": "Error"}
