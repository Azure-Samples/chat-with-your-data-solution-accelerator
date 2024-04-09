from unittest.mock import patch, Mock, ANY
import json

from backend.batch.GetConversationResponse import do_get_conversation_response


@patch("backend.batch.GetConversationResponse.Orchestrator")
def test_get_conversation_response(mock_create_message_orchestrator):
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


# @patch("backend.batch.BatchStartProcessing.create_queue_client")
# @patch("backend.batch.BatchStartProcessing.AzureBlobStorageClient")
# def test_batch_start_processing_filters_filter_no_embeddings(mock_blob_storage_client, mock_create_queue_client):
#     mock_http_request = Mock()
#     mock_http_request.params = dict()
#     mock_http_request.params["process_all"] = "false"

#     mock_queue_client = Mock()
#     mock_create_queue_client.return_value = mock_queue_client

#     mock_blob_storage_client.return_value.get_all_files.return_value = [
#         {
#             "filename": "file_name_one",
#             "embeddings_added": True  # will get filtered out
#         },
#         {
#             "filename": "file_name_two",
#             "embeddings_added": False
#         }
#     ]
#     response = do_batch_start_processing(mock_http_request)

#     assert response.status_code == 200

#     mock_queue_client.send_message.assert_called_once_with(
#         b'{"filename": "file_name_two"}',
#     )
