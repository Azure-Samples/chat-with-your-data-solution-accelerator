from unittest.mock import patch, MagicMock

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.plugins.post_answering_plugin import PostAnsweringPlugin
from semantic_kernel import Kernel


@patch("backend.batch.utilities.plugins.post_answering_plugin.PostPromptTool")
@pytest.mark.asyncio
async def test_validate_answer(PostPromptToolMock: MagicMock):
    # given
    kernel = Kernel()

    plugin = kernel.add_plugin(
        plugin=PostAnsweringPlugin(),
        plugin_name="PostAnswering",
    )
    answer = Answer(question="question", answer="answer")
    mock_answer = Answer(question="question", answer="mock-answer")

    PostPromptToolMock.return_value.validate_answer.return_value = mock_answer

    # when
    response = await kernel.invoke(plugin["validate_answer"], answer=answer)

    # then
    assert response is not None
    assert response.value == mock_answer

    PostPromptToolMock.return_value.validate_answer.assert_called_once_with(answer)
