from unittest.mock import ANY, AsyncMock, MagicMock, patch
import json

import pytest
from backend.batch.utilities.orchestrator.prompt_flow import (
    PromptFlowOrchestrator,
)
from backend.batch.utilities.parser.output_parser_tool import OutputParserTool

@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.orchestrator.prompt_flow.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value

        llm_helper.get_ml_client.return_value = MagicMock()
        llm_helper.get_endpoint_name.return_value = "endpoint_name"
        llm_helper.get_deployment_name.return_value = "deployment_name"
        llm_helper.transform_chat_history_for_pf.return_value = []

        yield llm_helper

@pytest.fixture()
def orchestrator():
    with patch(
        "backend.batch.utilities.orchestrator.prompt_flow.OrchestratorBase.__init__"
    ):
        orchestrator = PromptFlowOrchestrator()

        orchestrator.config = MagicMock()
        orchestrator.config.prompts.enable_content_safety = True

        orchestrator.call_content_safety_input = MagicMock(return_value=None)
        orchestrator.call_content_safety_output = MagicMock(return_value=None)

        orchestrator.output_parser = OutputParserTool()

        yield orchestrator

def test_prompt_flow_init(orchestrator: PromptFlowOrchestrator):
    assert orchestrator.ml_client is not None
    assert orchestrator.enpoint_name == "endpoint_name"
    assert orchestrator.deployment_name == "deployment_name"

@pytest.mark.asyncio
async def test_content_safety_input(orchestrator: PromptFlowOrchestrator):
    # given
    content_safety_response = [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "bad question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "Content safety response input.",
            "end_turn": True,
        },
    ]
    orchestrator.call_content_safety_input = MagicMock(
        return_value=content_safety_response
    )

    # when
    response = await orchestrator.orchestrate("bad question", [])

    # then
    assert response == content_safety_response

@pytest.mark.asyncio
async def test_orchestrate(orchestrator: PromptFlowOrchestrator):
    # given
    user_message = "question"
    chat_history = []
    expected_result = [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "answer",
            "end_turn": True,
        },
    ]
    chat_output = {"chat_output":"answer", "citations":["",[]]}

    orchestrator.call_content_safety_input = MagicMock(return_value=None)
    orchestrator.call_content_safety_output = MagicMock(return_value=None)
    orchestrator.ml_client.online_endpoints.invoke = AsyncMock(return_value=chat_output)

    # when
    with patch('json.loads', return_value=chat_output):
        response = await orchestrator.orchestrate(user_message, chat_history)

    # then
    orchestrator.call_content_safety_input.assert_called_once_with(user_message)
    orchestrator.call_content_safety_output.assert_called_once_with(user_message, "answer")
    orchestrator.llm_helper.transform_chat_history_for_pf.assert_called_once_with(chat_history)
    orchestrator.ml_client.online_endpoints.invoke.assert_called_once_with(
        endpoint_name="endpoint_name", request_file=ANY, deployment_name="deployment_name"
    )
    assert response == expected_result

@pytest.mark.asyncio
async def test_content_safety_output(orchestrator: PromptFlowOrchestrator):
    # given
    chat_output = {"chat_output":"bad-response", "citations":["",[]]}
    content_safety_response = [
        {
            "role": "tool",
            "content": "Content safety response output.",
            "end_turn": True,
        },
    ]
    orchestrator.call_content_safety_output.return_value = content_safety_response

    with patch.object(orchestrator.ml_client, 'invoke', new_callable=AsyncMock,
                      return_value=chat_output), patch('json.loads', return_value=chat_output):
        # when
        response = await orchestrator.orchestrate("question", [])

    # then
    orchestrator.call_content_safety_output.assert_called_once_with("question", "bad-response")
    assert response == content_safety_response
