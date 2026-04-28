"""Tests for `shared.tools.text_processing` (task #20b).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.tools.text_processing import (
    DEFAULT_SYSTEM_PROMPT,
    TextProcessingHelper,
)
from shared.types import ChatMessage


def _make_llm(reply_text: str = "ok") -> AsyncMock:
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply_text)
    )
    return llm


@pytest.mark.asyncio
async def test_process_returns_assistant_content() -> None:
    llm = _make_llm("Short summary.")
    helper = TextProcessingHelper(llm=llm)
    result = await helper.process("Long article body...", "Summarize")
    assert result == "Short summary."


@pytest.mark.asyncio
async def test_process_passes_default_system_prompt() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    await helper.process("hello", "Translate to French")
    messages = llm.chat.await_args.args[0]
    assert messages[0].role == "system"
    assert messages[0].content == DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_process_composes_operation_into_user_message() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    await helper.process("hello", "Translate to French")
    messages = llm.chat.await_args.args[0]
    assert messages[1].role == "user"
    assert "Translate to French" in messages[1].content
    assert "hello" in messages[1].content


@pytest.mark.asyncio
async def test_process_strips_whitespace_from_operation() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    await helper.process("hi", "  Summarize  ")
    user_content = llm.chat.await_args.args[0][1].content
    # No leading/trailing spaces around the operation verb.
    assert user_content.startswith("Summarize the following TEXT:")


@pytest.mark.asyncio
async def test_process_short_circuits_on_empty_text() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    assert await helper.process("", "Summarize") == ""
    assert await helper.process("   ", "Summarize") == ""
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_rejects_empty_operation() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    with pytest.raises(ValueError, match="operation"):
        await helper.process("hello", "")
    with pytest.raises(ValueError, match="operation"):
        await helper.process("hello", "   ")
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_passes_deployment_through() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    await helper.process("hi", "Summarize", deployment="gpt-4o-mini")
    assert llm.chat.await_args.kwargs["deployment"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_process_passes_none_deployment_by_default() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(llm=llm)
    await helper.process("hi", "Summarize")
    assert llm.chat.await_args.kwargs["deployment"] is None


@pytest.mark.asyncio
async def test_process_honors_custom_system_prompt() -> None:
    llm = _make_llm()
    helper = TextProcessingHelper(
        llm=llm, system_prompt="You are a strict legal editor."
    )
    await helper.process("hi", "Rewrite formally")
    assert (
        llm.chat.await_args.args[0][0].content
        == "You are a strict legal editor."
    )
