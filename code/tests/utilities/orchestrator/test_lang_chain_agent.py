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


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_with_content_safety_input_blocked(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()
    agent.config.prompts.enable_content_safety = True
    agent.config.prompts.enable_post_answering_prompt = False

    blocked_response = [{"role": "assistant", "content": "Content blocked"}]
    agent.call_content_safety_input = MagicMock(return_value=blocked_response)

    # When
    result = await agent.orchestrate(user_message="Harmful message", chat_history=[])

    # Then
    assert result == blocked_response
    agent.call_content_safety_input.assert_called_once_with("Harmful message")
    # Verify agent chain was never executed
    agent_executor_mock.assert_not_called()


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_with_content_safety_output_blocked(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()
    agent.config.prompts.enable_content_safety = True
    agent.config.prompts.enable_post_answering_prompt = False

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    agent_chain_mock.run.return_value = '{"question": "Hello", "answer": "Harmful response", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'

    blocked_response = [{"role": "assistant", "content": "Output blocked"}]
    agent.call_content_safety_input = MagicMock(return_value=None)
    agent.call_content_safety_output = MagicMock(return_value=blocked_response)

    # When
    result = await agent.orchestrate(user_message="Hello", chat_history=[])

    # Then
    assert result == blocked_response
    agent.call_content_safety_output.assert_called_once_with("Hello", "Harmful response")
    # Verify output parser was never called
    agent.output_parser.parse.assert_not_called()


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_with_chat_history_builds_memory(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()
    agent.config.prompts.enable_content_safety = False
    agent.config.prompts.enable_post_answering_prompt = False

    chat_history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Second question"},
        {"role": "assistant", "content": "Second answer"},
    ]

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    agent_chain_mock.run.return_value = '{"question": "Third question", "answer": "Third answer", "source_documents": [], "prompt_tokens": null, "completion_tokens": null}'

    agent.output_parser.parse.return_value = [{"role": "assistant", "content": "Third answer"}]

    # When
    await agent.orchestrate(user_message="Third question", chat_history=chat_history)

    # Then - verify memory was created (AgentExecutor.from_agent_and_tools called with memory)
    assert agent_executor_mock.called
    call_kwargs = agent_executor_mock.call_args[1]
    assert "memory" in call_kwargs
    memory = call_kwargs["memory"]
    # Verify memory has chat history (4 messages in history)
    assert len(memory.chat_memory.messages) == 4


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@pytest.mark.asyncio
async def test_orchestrate_with_answer_json_parse_exception_creates_fallback_answer(
    agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()
    agent.config.prompts.enable_content_safety = False
    agent.config.prompts.enable_post_answering_prompt = False

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    # Return plain text instead of JSON
    agent_chain_mock.run.return_value = "Plain text answer without JSON"

    agent.output_parser.parse.return_value = [{"role": "assistant", "content": "Plain text answer without JSON"}]

    # When
    await agent.orchestrate(user_message="Hello", chat_history=[])

    # Then - verify output parser was called with fallback Answer object
    agent.output_parser.parse.assert_called_once()
    call_kwargs = agent.output_parser.parse.call_args[1]
    assert call_kwargs["question"] == "Hello"
    assert call_kwargs["answer"] == "Plain text answer without JSON"
    assert call_kwargs["source_documents"] == []


@patch("backend.batch.utilities.orchestrator.lang_chain_agent.ZeroShotAgent")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.LLMChain")
@patch("langchain.agents.AgentExecutor.from_agent_and_tools")
@patch("backend.batch.utilities.orchestrator.lang_chain_agent.PostPromptTool")
@pytest.mark.asyncio
async def test_orchestrate_with_post_answering_prompt_validates_answer(
    post_prompt_tool_mock, agent_executor_mock, llm_chain_mock, zero_shot_agent_mock
):
    # Given
    agent = LangChainAgentNoInit()
    agent.config.prompts.enable_content_safety = False
    agent.config.prompts.enable_post_answering_prompt = True

    agent_chain_mock = MagicMock()
    agent_executor_mock.return_value = agent_chain_mock
    agent_chain_mock.run.return_value = '{"question": "Hello", "answer": "Original answer", "source_documents": [], "prompt_tokens": 10, "completion_tokens": 20}'

    # Mock PostPromptTool to return validated answer
    validated_answer = Answer(
        question="Hello",
        answer="Validated answer",
        source_documents=[],
        prompt_tokens=5,
        completion_tokens=10,
    )
    post_prompt_instance = MagicMock()
    post_prompt_tool_mock.return_value = post_prompt_instance
    post_prompt_instance.validate_answer.return_value = validated_answer

    agent.output_parser.parse.return_value = [{"role": "assistant", "content": "Validated answer"}]

    # When
    await agent.orchestrate(user_message="Hello", chat_history=[])

    # Then - verify post prompt validation was called
    post_prompt_instance.validate_answer.assert_called_once()
    # Verify output parser received validated answer
    agent.output_parser.parse.assert_called_once_with(
        question="Hello", answer="Validated answer", source_documents=[]
    )
