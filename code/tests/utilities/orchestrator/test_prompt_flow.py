from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from backend.batch.utilities.orchestrator.prompt_flow import (
    PromptFlowOrchestrator,
)
from backend.batch.utilities.parser.output_parser_tool import OutputParserTool


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.orchestrator.prompt_flow.LLMHelper") as mock:
        llm_helper = mock.return_value

        mock_ml_client = MagicMock()
        llm_helper.get_ml_client.return_value = mock_ml_client

        yield llm_helper, mock_ml_client


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.orchestrator.prompt_flow.EnvHelper") as mock:

        env_helper = mock.return_value

        env_helper.PROMPT_FLOW_ENDPOINT_NAME = "endpoint_name"
        env_helper.PROMPT_FLOW_DEPLOYMENT_NAME = "deployment_name"

        yield env_helper


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


def test_prompt_flow_init_initializes_with_expected_attributes(
    orchestrator: PromptFlowOrchestrator, llm_helper_mock
):
    _, mock_ml_client = llm_helper_mock
    assert orchestrator.ml_client is mock_ml_client
    assert orchestrator.enpoint_name == "endpoint_name"
    assert orchestrator.deployment_name == "deployment_name"


@pytest.mark.asyncio
async def test_orchestrate_returns_content_safety_response_for_unsafe_input(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    user_message = "bad question"
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
    orchestrator.call_content_safety_input.return_value = content_safety_response

    # when
    response = await orchestrator.orchestrate(user_message, [])

    # then
    orchestrator.call_content_safety_input.assert_called_once_with(user_message)
    assert response == content_safety_response


@pytest.mark.asyncio
async def test_orchestrate_returns_expected_chat_response(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    user_message = "question"
    chat_history = []
    expected_result = [
        {
            "role": "tool",
            "content": '{"citations": [{"content": "[None](some-filepath)\\n\\n\\nsome-content", "id": "[doc1]", "chunk_id": "1", "title": null, "filepath": "some-filepath", "url": "[None](some-filepath)", "metadata": {"offset": null, "source": "some-filepath", "markdown_url": "[None](some-filepath)", "title": null, "original_url": "some-filepath", "chunk": null, "key": "[doc1]", "filename": "some-filepath"}}, {"content": "[None](some-other-filepath)\\n\\n\\nsome-other-content", "id": "[doc2]", "chunk_id": "2", "title": null, "filepath": "some-other-filepath", "url": "[None](some-other-filepath)", "metadata": {"offset": null, "source": "some-other-filepath", "markdown_url": "[None](some-other-filepath)", "title": null, "original_url": "some-other-filepath", "chunk": null, "key": "[doc2]", "filename": "some-other-filepath"}}], "intent": "question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "answer[doc1][doc2]",
            "end_turn": True,
        },
    ]
    chat_output = {
        "chat_output": "answer[doc1][doc2]",
        "citations": {
            "[doc1]": {
                "content": "some-content",
                "filepath": "some-filepath",
                "chunk_id": 1,
            },
            "[doc2]": {
                "content": "some-other-content",
                "filepath": "some-other-filepath",
                "chunk_id": 2,
            },
        },
    }

    orchestrator.transform_chat_history = MagicMock(return_value=[])
    orchestrator.ml_client.online_endpoints.invoke = AsyncMock(return_value=chat_output)

    # when
    with patch("json.loads", return_value=chat_output):
        response = await orchestrator.orchestrate(user_message, chat_history)

    # then
    orchestrator.transform_chat_history.assert_called_once_with(chat_history)
    orchestrator.ml_client.online_endpoints.invoke.assert_called_once_with(
        endpoint_name="endpoint_name",
        request_file=ANY,
        deployment_name="deployment_name",
    )
    assert response == expected_result


@pytest.mark.asyncio
async def test_orchestrate_returns_error_response(orchestrator: PromptFlowOrchestrator):
    # given
    user_message = "question"
    chat_history = []
    error = Exception()
    orchestrator.ml_client.online_endpoints.invoke = AsyncMock(side_effect=error)

    # when & then
    with pytest.raises(RuntimeError):
        await orchestrator.orchestrate(user_message, chat_history)


@pytest.mark.asyncio
async def test_orchestrate_returns_content_safety_response_for_unsafe_output(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    user_message = "question"
    chat_output = {"chat_output": "bad-response", "citations": {}}
    content_safety_response = [
        {
            "role": "tool",
            "content": "Content safety response output.",
            "end_turn": True,
        },
    ]
    orchestrator.call_content_safety_output.return_value = content_safety_response

    with patch.object(
        orchestrator.ml_client,
        "invoke",
        new_callable=AsyncMock,
        return_value=chat_output,
    ), patch("json.loads", return_value=chat_output):
        # when
        response = await orchestrator.orchestrate(user_message, [])

    # then
    orchestrator.call_content_safety_output.assert_called_once_with(
        user_message, "bad-response"
    )
    assert response == content_safety_response


def test_transform_chat_history_returns_expected_format(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    chat_history = [
        {"role": "user", "content": "Hi!"},
        {
            "content": "Hello! How can I assist you today?",
            "end_turn": True,
            "role": "assistant",
        },
    ]

    # when
    result = orchestrator.transform_chat_history(chat_history)

    # then
    expected_result = [
        {
            "inputs": {"chat_input": "Hi!"},
            "outputs": {"chat_output": "Hello! How can I assist you today?"},
        }
    ]
    assert result == expected_result


def test_transform_chat_history_returns_empty_for_no_chat_history(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    chat_history = []

    # when
    result = orchestrator.transform_chat_history(chat_history)

    # then
    assert result == []


def test_transform_chat_history_handles_multiple_messages_correctly(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    chat_history = [
        {"role": "user", "content": "Hi!"},
        {
            "content": "Hello! How can I assist you today?",
            "end_turn": True,
            "role": "assistant",
        },
        {"role": "user", "content": "Can you help with employee benefits?"},
        {
            "content": "What information are you looking for?",
            "end_turn": True,
            "role": "assistant",
        },
    ]

    # when
    result = orchestrator.transform_chat_history(chat_history)

    # then
    expected_result = [
        {
            "inputs": {"chat_input": "Hi!"},
            "outputs": {"chat_output": "Hello! How can I assist you today?"},
        },
        {
            "inputs": {"chat_input": "Can you help with employee benefits?"},
            "outputs": {"chat_output": "What information are you looking for?"},
        },
    ]
    assert result == expected_result


def test_transform_chat_history_handles_no_assistant_message_correctly(
    orchestrator: PromptFlowOrchestrator,
):
    # given
    chat_history = [
        {"role": "user", "content": "Hi!"},
        {"role": "user", "content": "Hello!"},
        {
            "content": "Hello! How can I assist you today?",
            "end_turn": True,
            "role": "assistant",
        },
    ]

    # when
    result = orchestrator.transform_chat_history(chat_history)

    # then
    expected_result = [
        {"inputs": {"chat_input": "Hi!"}, "outputs": {"chat_output": ""}},
        {
            "inputs": {"chat_input": "Hello!"},
            "outputs": {"chat_output": "Hello! How can I assist you today?"},
        },
    ]
    assert result == expected_result
