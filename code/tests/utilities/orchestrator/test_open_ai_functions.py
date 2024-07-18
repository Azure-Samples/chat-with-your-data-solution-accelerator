from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.orchestrator.open_ai_functions import (
    OpenAIFunctionsOrchestrator,
)
from backend.batch.utilities.parser.output_parser_tool import OutputParserTool


@pytest.fixture(autouse=True)
def llm_helper_mock():
    with patch(
        "backend.batch.utilities.orchestrator.open_ai_functions.LLMHelper"
    ) as mock:
        llm_helper = mock.return_value

        yield llm_helper


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
async def test_content_safety_input(orchestrator: OpenAIFunctionsOrchestrator):
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
