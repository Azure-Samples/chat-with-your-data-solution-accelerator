"""Tests for `shared.tools.qa` (task #20d).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.tools.qa import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    QAResult,
    QuestionAnsweringHelper,
)
from shared.types import ChatMessage, SearchResult


def _src(idx: int, content: str, **extra: object) -> SearchResult:
    return SearchResult(id=f"doc-{idx}", content=content, **extra)  # type: ignore[arg-type]


def _make_llm(reply_text: str = "Grounded answer.") -> AsyncMock:
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply_text)
    )
    return llm


def _make_search(results: list[SearchResult] | None = None) -> AsyncMock:
    search = AsyncMock()
    search.search = AsyncMock(return_value=list(results or []))
    return search


@pytest.mark.asyncio
async def test_answer_returns_qa_result_with_answer_and_sources() -> None:
    sources = [_src(1, "alpha"), _src(2, "beta")]
    llm = _make_llm("Final answer [doc1].")
    search = _make_search(sources)
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    result = await helper.answer("What is alpha?")
    assert isinstance(result, QAResult)
    assert result.answer == "Final answer [doc1]."
    assert result.sources == sources


@pytest.mark.asyncio
async def test_answer_calls_search_with_question() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("query?")
    assert search.search.await_args.args[0] == "query?"


@pytest.mark.asyncio
async def test_answer_passes_top_k_to_search() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("q?", top_k=7)
    assert search.search.await_args.kwargs["top_k"] == 7


@pytest.mark.asyncio
async def test_answer_default_top_k_is_none() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("q?")
    assert search.search.await_args.kwargs["top_k"] is None


@pytest.mark.asyncio
async def test_answer_passes_deployment_to_llm() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("q?", deployment="gpt-4o")
    assert llm.chat.await_args.kwargs["deployment"] == "gpt-4o"


@pytest.mark.asyncio
async def test_answer_short_circuits_on_empty_question() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    result = await helper.answer("")
    assert result.answer == ""
    assert result.sources == []
    search.search.assert_not_awaited()
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_answer_short_circuits_on_whitespace_question() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    result = await helper.answer("   \n")
    assert result.answer == ""
    search.search.assert_not_awaited()
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_answer_includes_sources_in_user_prompt() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "alpha"), _src(2, "beta")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("q?")
    messages = llm.chat.await_args.args[0]
    user_content = messages[-1].content
    assert "[doc1]: alpha" in user_content
    assert "[doc2]: beta" in user_content


@pytest.mark.asyncio
async def test_answer_uses_default_system_prompt() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    await helper.answer("q?")
    messages = llm.chat.await_args.args[0]
    assert messages[0].role == "system"
    assert messages[0].content == DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_answer_inserts_chat_history_between_system_and_user() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    history = [
        ChatMessage(role="user", content="prior?"),
        ChatMessage(role="assistant", content="prior answer"),
    ]
    await helper.answer("now?", chat_history=history)
    messages = llm.chat.await_args.args[0]
    # system, prior_user, prior_assistant, current_user
    assert len(messages) == 4
    assert messages[0].role == "system"
    assert messages[1].content == "prior?"
    assert messages[2].content == "prior answer"
    assert messages[3].role == "user"


@pytest.mark.asyncio
async def test_answer_handles_no_search_results() -> None:
    llm = _make_llm("I don't know.")
    search = _make_search([])
    helper = QuestionAnsweringHelper(llm=llm, search=search)
    result = await helper.answer("q?")
    assert result.answer == "I don't know."
    assert result.sources == []
    user_content = llm.chat.await_args.args[0][-1].content
    # No source block when retrieval returned nothing.
    assert "[doc1]" not in user_content


@pytest.mark.asyncio
async def test_answer_honors_custom_system_and_user_prompts() -> None:
    llm = _make_llm()
    search = _make_search([_src(1, "x")])
    helper = QuestionAnsweringHelper(
        llm=llm,
        search=search,
        system_prompt="STRICT",
        user_prompt="Q={question} | S={sources}",
    )
    await helper.answer("hi?")
    messages = llm.chat.await_args.args[0]
    assert messages[0].content == "STRICT"
    assert messages[-1].content == "Q=hi? | S=[doc1]: x"


def test_default_prompts_are_well_formed() -> None:
    assert "{question}" in DEFAULT_USER_PROMPT
    assert "{sources}" in DEFAULT_USER_PROMPT
    assert isinstance(DEFAULT_SYSTEM_PROMPT, str) and DEFAULT_SYSTEM_PROMPT
