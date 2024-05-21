from unittest.mock import MagicMock, patch
import pytest

from backend.batch.utilities.orchestrator.lang_chain_agent import LangChainAgent
from backend.batch.utilities.common.answer import Answer


class LangChainAgentNoInit(LangChainAgent):
    def __init__(self) -> None:
        self.content_safety_checker = MagicMock()
        self.question_answer_tool = MagicMock()
        self.text_processing_tool = MagicMock()
        self.config = MagicMock()
        self.output_parser = MagicMock()
        self.tools = MagicMock()
        self.llm_helper = MagicMock()
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}


def test_run_tool_returns_answer_json():
    # Given
    user_message = "Hello"
    agent = LangChainAgentNoInit()
    answer = Answer(
        question=user_message,
        answer="Hello, how can I help you?",
        source_documents=[],
        prompt_tokens=None,
        completion_tokens=None,
    )
    agent.question_answer_tool.answer_question = MagicMock(return_value=answer)

    # When
    answer_json = agent.run_tool(user_message)

    # Then
    assert (
        answer_json
        == '{"question": "Hello", "answer": "Hello, how can I help you?", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'
    )
    agent.question_answer_tool.answer_question.assert_called_once_with(
        user_message, chat_history=[]
    )


def test_run_text_processing_tool_returns_answer_json():
    # Given
    user_message = "Hello"
    agent = LangChainAgentNoInit()
    answer = Answer(
        question=user_message,
        answer="Hello, how can I help you?",
        source_documents=[],
        prompt_tokens=None,
        completion_tokens=None,
    )
    agent.text_processing_tool.answer_question = MagicMock(return_value=answer)

    # When
    answer_json = agent.run_text_processing_tool(user_message)

    # Then
    assert (
        answer_json
        == '{"question": "Hello", "answer": "Hello, how can I help you?", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'
    )
    agent.text_processing_tool.answer_question.assert_called_once_with(
        user_message, chat_history=[]
    )


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_langchain_to_orchestrate_chat(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()

    agent.config.prompts.enable_post_answering_prompt = False
    agent.config.prompts.enable_content_safety = False

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    agent_chain_mock.run.return_value = '{"question": "Hello", "answer": "Hello, how can I help you?", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'

    expected_messages = [{"some", "message"}, {"another", "message"}]
    agent.output_parser.parse.return_value = expected_messages

    # When
    actual_messages = await agent.orchestrate(user_message="Hello", chat_history=[])

    # Then
    assert actual_messages == expected_messages
    agent_chain_mock.run.assert_called_once_with("Hello")
    agent.output_parser.parse.assert_called_once_with(
        question="Hello", answer="Hello, how can I help you?", source_documents=[]
    )


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_returns_error_message_on_Exception(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()

    agent.config.prompts.enable_post_answering_prompt = False
    agent.config.prompts.enable_content_safety = False

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    agent_chain_mock.run.side_effect = Exception("Some error")

    agent.output_parser.parse.return_value = [{"some", "message"}]

    # When + Then
    with pytest.raises(Exception):
        await agent.orchestrate(user_message="Hello", chat_history=[])
