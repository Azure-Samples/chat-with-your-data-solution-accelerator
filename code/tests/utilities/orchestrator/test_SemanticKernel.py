from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.orchestrator.SemanticKernel import (
    SemanticKernelOrchestrator,
)
from backend.batch.utilities.parser.OutputParserTool import OutputParserTool
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.function_call_behavior import EnabledFunctions
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents.author_role import AuthorRole
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.finish_reason import FinishReason
from semantic_kernel.contents.function_call_content import FunctionCallContent

chat_message_default_content = ChatMessageContent(
    content="mock-response",
    role=AuthorRole.ASSISTANT,
    metadata={
        "usage": MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
        )
    },
)


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch("backend.batch.utilities.orchestrator.SemanticKernel.LLMHelper") as mock:
        llm_helper = mock.return_value

        llm_helper.get_sk_chat_completion_service.return_value = AzureChatCompletion(
            service_id="mock-service-id",
            deployment_name="mock-deployment",
            endpoint="https://mock-endpoint",
            api_key="mock-api-key",
        )

        llm_helper.get_sk_service_settings.return_value = (
            AzureChatPromptExecutionSettings(
                service_id="mock-service-id", temperature=0, max_tokens=1000
            )
        )

        yield llm_helper


@pytest.fixture()
def orchestrator():
    with patch(
        "backend.batch.utilities.orchestrator.SemanticKernel.OrchestratorBase.__init__"
    ):
        orchestrator = SemanticKernelOrchestrator()

        orchestrator.tokens = {"prompt": 0, "completion": 0, "total": 0}

        orchestrator.config = MagicMock()
        orchestrator.config.prompts.enable_content_safety = True
        orchestrator.config.prompts.enable_post_answering_prompt = True

        orchestrator.call_content_safety_input = MagicMock(return_value=None)
        orchestrator.call_content_safety_output = MagicMock(return_value=None)

        orchestrator.output_parser = OutputParserTool()

        yield orchestrator


def test_kernel_init(orchestrator: SemanticKernelOrchestrator):
    assert isinstance(orchestrator.kernel, Kernel)

    assert orchestrator.kernel.services["mock-service-id"] is not None
    assert orchestrator.kernel.services["mock-service-id"] is orchestrator.chat_service

    assert orchestrator.kernel.plugins["PostAnswering"] is not None
    assert (
        orchestrator.kernel.plugins["PostAnswering"].functions["validate_answer"]
        is not None
    )


@pytest.mark.asyncio
async def test_content_safety_input(orchestrator: SemanticKernelOrchestrator):
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
async def test_semantic_kernel_no_function_call(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.return_value.value = [chat_message_default_content]

        # when
        response = await orchestrator.orchestrate("question", [])

    # then
    assert response == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "mock-response",
            "end_turn": True,
        },
    ]

    kernel_mock.invoke.assert_awaited_once_with(
        function=ANY,
        chat_history=ANY,
        user_message="question",
    )

    assert orchestrator.tokens == {"prompt": 10, "completion": 20, "total": 30}


@pytest.mark.asyncio
async def test_chat_plugin_added(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.return_value.value = [chat_message_default_content]

        # when
        await orchestrator.orchestrate("question", [])

    # then
    assert kernel_mock.plugins["Chat"] is not None
    assert kernel_mock.plugins["Chat"].functions["search_documents"] is not None
    assert kernel_mock.plugins["Chat"].functions["text_processing"] is not None


@pytest.mark.asyncio
async def test_kernel_function_call_behavior(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.return_value.value = [chat_message_default_content]

        # when
        await orchestrator.orchestrate("question", [])

    # then
    function_call_behavior: EnabledFunctions = (
        kernel_mock.add_function.call_args.kwargs[
            "prompt_execution_settings"
        ].function_call_behavior
    )

    assert function_call_behavior.auto_invoke_kernel_functions is False
    assert function_call_behavior.enable_kernel_functions is True
    assert function_call_behavior.filters == {"included_plugins": ["Chat"]}


@pytest.mark.asyncio
async def test_semantic_kernel_text_processing(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    question = "question"

    first_response = ChatMessageContent(
        role=AuthorRole.ASSISTANT,
        finish_reason=FinishReason.TOOL_CALLS,
        items=[
            FunctionCallContent(
                id="id",
                name="Chat-text_processing",
                arguments='{"text": "mock-text", "operation": "mock-operation"}',
            )
        ],
        metadata={
            "usage": MagicMock(
                prompt_tokens=100,
                completion_tokens=200,
            )
        },
    )

    tool_response = Answer(
        question=question,
        answer="mock-text-processing-answer",
        prompt_tokens=10,
        completion_tokens=20,
    )

    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.side_effect = [
            MagicMock(value=[first_response]),
            MagicMock(value=tool_response),
        ]

        # when
        response = await orchestrator.orchestrate(question, [])

    # then
    assert response == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "mock-text-processing-answer",
            "end_turn": True,
        },
    ]

    assert kernel_mock.invoke.await_count == 2

    kernel_mock.invoke.assert_awaited_with(
        function=ANY,
        text="mock-text",
        operation="mock-operation",
    )

    assert orchestrator.tokens == {"prompt": 110, "completion": 220, "total": 330}


@pytest.mark.asyncio
async def test_semantic_kernel_search_documents_post_answering_prompt(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    first_response = ChatMessageContent(
        role=AuthorRole.ASSISTANT,
        finish_reason=FinishReason.TOOL_CALLS,
        items=[
            FunctionCallContent(
                id="id",
                name="Chat-search_documents",
                arguments='{"question": "mock-tool-question"}',
            )
        ],
        metadata={
            "usage": MagicMock(
                prompt_tokens=100,
                completion_tokens=200,
            )
        },
    )

    tool_response = Answer(
        question="mock-tool-question",
        answer="mock-search-documents-answer",
        prompt_tokens=10,
        completion_tokens=20,
    )

    post_answering_response = Answer(
        question="mock-tool-question",
        answer="mock-post-answering-response",
        prompt_tokens=50,
        completion_tokens=60,
    )

    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.side_effect = [
            MagicMock(value=[first_response]),
            MagicMock(value=tool_response),
            MagicMock(value=post_answering_response),
        ]

        # when
        response = await orchestrator.orchestrate("question", [])

    # then
    assert response == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "mock-tool-question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "mock-post-answering-response",
            "end_turn": True,
        },
    ]

    assert kernel_mock.invoke.await_count == 3

    kernel_mock.invoke.assert_has_awaits(
        [
            call(
                function=ANY,
                question="mock-tool-question",
            ),
            call(
                function_name="validate_answer",
                plugin_name="PostAnswering",
                answer=tool_response,
            ),
        ]
    )

    assert orchestrator.tokens == {"prompt": 160, "completion": 280, "total": 440}


@pytest.mark.asyncio
async def test_semantic_kernel_search_documents_without_post_answering_prompt(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    orchestrator.config.prompts.enable_post_answering_prompt = False

    first_response = ChatMessageContent(
        role=AuthorRole.ASSISTANT,
        finish_reason=FinishReason.TOOL_CALLS,
        items=[
            FunctionCallContent(
                id="id",
                name="Chat-search_documents",
                arguments='{"question": "mock-tool-question"}',
            )
        ],
        metadata={
            "usage": MagicMock(
                prompt_tokens=100,
                completion_tokens=200,
            )
        },
    )

    tool_response = Answer(
        question="mock-tool-question",
        answer="mock-search-documents-answer",
        prompt_tokens=10,
        completion_tokens=20,
    )

    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.side_effect = [
            MagicMock(value=[first_response]),
            MagicMock(value=tool_response),
        ]

        # when
        response = await orchestrator.orchestrate("question", [])

    # then
    assert response == [
        {
            "role": "tool",
            "content": '{"citations": [], "intent": "mock-tool-question"}',
            "end_turn": False,
        },
        {
            "role": "assistant",
            "content": "mock-search-documents-answer",
            "end_turn": True,
        },
    ]

    assert kernel_mock.invoke.await_count == 2

    kernel_mock.invoke.assert_awaited_with(
        function=ANY,
        question="mock-tool-question",
    )

    assert orchestrator.tokens == {"prompt": 110, "completion": 220, "total": 330}


@pytest.mark.asyncio
async def test_chat_history_included(
    orchestrator: SemanticKernelOrchestrator,
):
    # given
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help you today?"},
    ]

    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.return_value.value = [chat_message_default_content]

        # when
        await orchestrator.orchestrate("question", chat_history)

    # then
    chat_history = kernel_mock.invoke.call_args.kwargs["chat_history"]
    messages = chat_history.messages

    assert len(messages) == 3
    assert messages[0].role == AuthorRole.SYSTEM

    assert messages[1].role == AuthorRole.USER
    assert messages[1].content == "Hello"

    assert messages[2].role == AuthorRole.ASSISTANT
    assert messages[2].content == "Hi, how can I help you today?"


@pytest.mark.asyncio
async def test_content_safety_output(orchestrator: SemanticKernelOrchestrator):
    # given
    chat_message_content = ChatMessageContent(
        content="bad-response",
        role=AuthorRole.ASSISTANT,
        metadata={
            "usage": MagicMock(
                prompt_tokens=10,
                completion_tokens=20,
            )
        },
    )

    content_safety_response = [
        {
            "role": "assistant",
            "content": "Content safety response output.",
            "end_turn": True,
        },
    ]
    orchestrator.call_content_safety_output.return_value = content_safety_response

    with patch.object(orchestrator, "kernel", wraps=orchestrator.kernel) as kernel_mock:
        kernel_mock.invoke = AsyncMock()
        kernel_mock.invoke.return_value.value = [chat_message_content]

        # when
        response = await orchestrator.orchestrate("question", [])

    # then
    assert response == content_safety_response
