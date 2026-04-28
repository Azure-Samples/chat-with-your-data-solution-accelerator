"""Tests for `shared.tools.post_prompt` (task #20c).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.tools.post_prompt import (
    DEFAULT_FILTER_MESSAGE,
    DEFAULT_VALIDATION_PROMPT,
    PostPromptValidator,
    ValidationResult,
)
from shared.types import ChatMessage, SearchResult


def _make_llm(reply_text: str) -> AsyncMock:
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply_text)
    )
    return llm


def _src(idx: int, content: str) -> SearchResult:
    return SearchResult(id=f"doc-{idx}", content=content)


@pytest.mark.asyncio
async def test_validate_returns_original_answer_when_grounded() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate(
        "Q?", "Grounded answer.", [_src(1, "supporting text")]
    )
    assert isinstance(result, ValidationResult)
    assert result.grounded is True
    assert result.answer == "Grounded answer."


@pytest.mark.asyncio
async def test_validate_returns_filter_message_when_ungrounded() -> None:
    llm = _make_llm("false")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "Hallucinated.", [_src(1, "x")])
    assert result.grounded is False
    assert result.answer == DEFAULT_FILTER_MESSAGE


@pytest.mark.asyncio
async def test_validate_accepts_yes_as_grounded() -> None:
    llm = _make_llm("yes")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "A.", [_src(1, "x")])
    assert result.grounded is True


@pytest.mark.asyncio
async def test_validate_handles_punctuation_and_case() -> None:
    llm = _make_llm("  TRUE.  ")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "A.", [_src(1, "x")])
    assert result.grounded is True


@pytest.mark.asyncio
async def test_validate_unrecognized_verdict_is_ungrounded() -> None:
    llm = _make_llm("maybe?")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "A.", [_src(1, "x")])
    assert result.grounded is False
    assert result.answer == DEFAULT_FILTER_MESSAGE


@pytest.mark.asyncio
async def test_validate_short_circuits_on_empty_answer() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "", [_src(1, "x")])
    assert result.grounded is False
    assert result.answer == DEFAULT_FILTER_MESSAGE
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_short_circuits_on_whitespace_answer() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "   \n", [_src(1, "x")])
    assert result.grounded is False
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_formats_sources_with_doc_indices() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    await validator.validate(
        "Q?", "A.", [_src(1, "alpha"), _src(2, "beta")]
    )
    prompt = llm.chat.await_args.args[0][0].content
    assert "[doc1]: alpha" in prompt
    assert "[doc2]: beta" in prompt


@pytest.mark.asyncio
async def test_validate_handles_no_sources() -> None:
    llm = _make_llm("false")
    validator = PostPromptValidator(llm=llm)
    result = await validator.validate("Q?", "A.", [])
    # Without sources the model effectively has nothing to ground
    # against; verdict propagates as-is.
    assert result.grounded is False


@pytest.mark.asyncio
async def test_validate_uses_default_prompt_template() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    await validator.validate("What is X?", "X is Y.", [_src(1, "X is Y")])
    prompt = llm.chat.await_args.args[0][0].content
    assert "QUESTION:\nWhat is X?" in prompt
    assert "ANSWER:\nX is Y." in prompt


@pytest.mark.asyncio
async def test_validate_honors_custom_filter_message() -> None:
    llm = _make_llm("false")
    validator = PostPromptValidator(
        llm=llm, filter_message="Refusing this answer."
    )
    result = await validator.validate("Q?", "A.", [_src(1, "x")])
    assert result.answer == "Refusing this answer."


@pytest.mark.asyncio
async def test_validate_honors_custom_validation_prompt() -> None:
    llm = _make_llm("true")
    custom = "Check {question}|{answer}|{sources}"
    validator = PostPromptValidator(llm=llm, validation_prompt=custom)
    await validator.validate("Q?", "A.", [_src(1, "x")])
    prompt = llm.chat.await_args.args[0][0].content
    assert prompt == "Check Q?|A.|[doc1]: x"


@pytest.mark.asyncio
async def test_validate_passes_deployment_through() -> None:
    llm = _make_llm("true")
    validator = PostPromptValidator(llm=llm)
    await validator.validate("Q?", "A.", [_src(1, "x")], deployment="gpt-4o")
    assert llm.chat.await_args.kwargs["deployment"] == "gpt-4o"


def test_default_constants_are_strings() -> None:
    # Sanity: prompt + filter constants are non-empty strings the
    # caller can override but shouldn't have to.
    assert isinstance(DEFAULT_VALIDATION_PROMPT, str)
    assert "{question}" in DEFAULT_VALIDATION_PROMPT
    assert "{answer}" in DEFAULT_VALIDATION_PROMPT
    assert "{sources}" in DEFAULT_VALIDATION_PROMPT
    assert isinstance(DEFAULT_FILTER_MESSAGE, str) and DEFAULT_FILTER_MESSAGE
