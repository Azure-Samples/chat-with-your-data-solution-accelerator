from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.orchestrator.open_ai_functions import (
    OpenAIFunctionsOrchestrator,
)
from backend.batch.utilities.parser.output_parser_tool import OutputParserTool
from backend.batch.utilities.common.answer import Answer


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.orchestrator.open_ai_functions.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value

        yield llm_helper


@pytest.fixture
def env_helper_mock():
    with patch(
        "backend.batch.utilities.orchestrator.open_ai_functions.EnvHelper"
    ) as mock:
        env_helper = mock.return_value
        env_helper.OPEN_AI_FUNCTIONS_SYSTEM_PROMPT = "Test system prompt"
        yield env_helper


@pytest.fixture()
def orchestrator():
    with patch(
        "backend.batch.utilities.orchestrator.open_ai_functions.OrchestratorBase.__init__"
    ):
        orchestrator = OpenAIFunctionsOrchestrator()

        orchestrator.tokens = {"prompt": 0, "completion": 0, "total": 0}

        orchestrator.config = MagicMock()
        orchestrator.config.prompts.enable_content_safety = True
        orchestrator.config.prompts.enable_post_answering_prompt = True

        orchestrator.call_content_safety_input = MagicMock(return_value=None)
        orchestrator.call_content_safety_output = MagicMock(return_value=None)

        orchestrator.output_parser = OutputParserTool()

        yield orchestrator


@pytest.mark.asyncio
async def test_orchestrate_with_content_safety_input_blocked(
    orchestrator: OpenAIFunctionsOrchestrator,
):
    """Test content safety blocks harmful input before LLM call."""
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


@patch("backend.batch.utilities.orchestrator.open_ai_functions.QuestionAnswerTool")
@pytest.mark.asyncio
async def test_orchestrate_with_search_documents_function_call(
    qa_tool_mock,
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test orchestration with search_documents function call."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response with function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "function_call"
    mock_result.choices[0].message.function_call.name = "search_documents"
    mock_result.choices[0].message.function_call.arguments = '{"question": "What is Azure?"}'
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # Mock QuestionAnswerTool
    answer = Answer(
        question="What is Azure?",
        answer="Azure is Microsoft's cloud platform",
        source_documents=[],
        prompt_tokens=5,
        completion_tokens=10,
    )
    qa_tool_instance = qa_tool_mock.return_value
    qa_tool_instance.answer_question.return_value = answer

    # when
    response = await orchestrator.orchestrate("What is Azure?", [])

    # then
    qa_tool_instance.answer_question.assert_called_once_with(
        "What is Azure?", []
    )
    assert len(response) > 0


@patch("backend.batch.utilities.orchestrator.open_ai_functions.TextProcessingTool")
@pytest.mark.asyncio
async def test_orchestrate_with_text_processing_function_call(
    text_tool_mock,
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test orchestration with text_processing function call."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response with text_processing function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "function_call"
    mock_result.choices[0].message.function_call.name = "text_processing"
    mock_result.choices[0].message.function_call.arguments = (
        '{"text": "Hello world", "operation": "translate to Spanish"}'
    )
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # Mock TextProcessingTool
    answer = Answer(
        question="translate to Spanish: Hello world",
        answer="Hola mundo",
        source_documents=[],
        prompt_tokens=5,
        completion_tokens=10,
    )
    text_tool_instance = text_tool_mock.return_value
    text_tool_instance.answer_question.return_value = answer

    # when
    response = await orchestrator.orchestrate(
        "translate to Spanish: Hello world", []
    )

    # then
    text_tool_instance.answer_question.assert_called_once_with(
        "translate to Spanish: Hello world",
        [],
        text="Hello world",
        operation="translate to Spanish",
    )
    assert len(response) > 0


@pytest.mark.asyncio
async def test_orchestrate_with_no_function_call(
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test orchestration when LLM returns direct response without function call."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response without function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "stop"
    mock_result.choices[0].message.content = "Direct response from LLM"
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # when
    response = await orchestrator.orchestrate("Simple question", [])

    # then
    assert len(response) > 0
    # Verify Answer was created from direct response
    assert any("Direct response from LLM" in str(r) for r in response)


@pytest.mark.asyncio
async def test_orchestrate_with_unknown_function_call(
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test orchestration with unknown function call falls back to content response."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response with unknown function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "function_call"
    mock_result.choices[0].message.function_call.name = "unknown_function"
    mock_result.choices[0].message.content = "Unknown function response"
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # when
    response = await orchestrator.orchestrate("Question", [])

    # then
    assert len(response) > 0


@patch("backend.batch.utilities.orchestrator.open_ai_functions.PostPromptTool")
@patch("backend.batch.utilities.orchestrator.open_ai_functions.QuestionAnswerTool")
@pytest.mark.asyncio
async def test_orchestrate_with_post_answering_prompt_enabled(
    qa_tool_mock,
    post_tool_mock,
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test post-answering prompt validation when enabled."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = True

    # Mock LLM response with search_documents function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "function_call"
    mock_result.choices[0].message.function_call.name = "search_documents"
    mock_result.choices[0].message.function_call.arguments = (
        '{"question": "Test question"}'
    )
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # Mock QuestionAnswerTool and PostPromptTool
    initial_answer = Answer(
        question="Test question",
        answer="Initial answer",
        source_documents=[],
        prompt_tokens=5,
        completion_tokens=10,
    )
    validated_answer = Answer(
        question="Test question",
        answer="Validated answer",
        source_documents=[],
        prompt_tokens=3,
        completion_tokens=7,
    )

    qa_tool_instance = qa_tool_mock.return_value
    qa_tool_instance.answer_question.return_value = initial_answer

    post_tool_instance = post_tool_mock.return_value
    post_tool_instance.validate_answer.return_value = validated_answer

    # when
    response = await orchestrator.orchestrate("Test question", [])

    # then
    post_tool_instance.validate_answer.assert_called_once_with(initial_answer)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_orchestrate_with_content_safety_output_blocked(
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test content safety blocks harmful output after answer generation."""
    orchestrator.config.prompts.enable_content_safety = True
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "stop"
    mock_result.choices[0].message.content = "Harmful response"
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # Mock content safety output block
    content_safety_response = [
        {"role": "assistant", "content": "Output blocked by content safety"}
    ]
    orchestrator.call_content_safety_output = MagicMock(
        return_value=content_safety_response
    )

    # when
    response = await orchestrator.orchestrate("Question", [])

    # then
    assert response == content_safety_response
    orchestrator.call_content_safety_output.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrate_with_chat_history_builds_messages(
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test chat history is properly converted to messages for LLM."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    chat_history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Second question"},
    ]

    # Mock LLM response
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "stop"
    mock_result.choices[0].message.content = "Response"
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # when
    await orchestrator.orchestrate("Third question", chat_history)

    # then
    call_args = llm_helper_mock.get_chat_completion_with_functions.call_args[0]
    messages = call_args[0]

    # Verify message structure: system + chat history + current user message
    assert len(messages) == 5  # 1 system + 3 history + 1 current
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "First question"
    assert messages[4]["role"] == "user"
    assert messages[4]["content"] == "Third question"


@patch("backend.batch.utilities.orchestrator.open_ai_functions.QuestionAnswerTool")
@pytest.mark.asyncio
async def test_orchestrate_with_null_answer_gets_default_message(
    qa_tool_mock,
    orchestrator: OpenAIFunctionsOrchestrator,
    llm_helper_mock,
    env_helper_mock,
):
    """Test null answer is replaced with default message."""
    orchestrator.config.prompts.enable_content_safety = False
    orchestrator.config.prompts.enable_post_answering_prompt = False

    # Mock LLM response with function call
    mock_result = MagicMock()
    mock_result.choices = [MagicMock()]
    mock_result.choices[0].finish_reason = "function_call"
    mock_result.choices[0].message.function_call.name = "search_documents"
    mock_result.choices[0].message.function_call.arguments = '{"question": "Test"}'
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20

    llm_helper_mock.get_chat_completion_with_functions.return_value = mock_result

    # Mock QuestionAnswerTool returning answer with None
    answer = Answer(
        question="Test",
        answer=None,  # Null answer
        source_documents=[],
        prompt_tokens=5,
        completion_tokens=10,
    )
    qa_tool_instance = qa_tool_mock.return_value
    qa_tool_instance.answer_question.return_value = answer

    # when
    response = await orchestrator.orchestrate("Test", [])

    # then
    # Verify default message is set
    assert any(
        "requested information is not available" in str(r).lower()
        for r in response
    )
