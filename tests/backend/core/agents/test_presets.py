"""Tests for `backend.core.agents.presets` (assistant-type prompt presets, ADR 0030)."""

from enum import StrEnum

from backend.core.agents import presets
from backend.core.agents.presets import (
    ASSISTANT_PRESETS,
    DEFAULT_ASSISTANT_TYPE,
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
    AssistantType,
    body_for,
)


# ---------------------------------------------------------------------------
# AssistantType enum
# ---------------------------------------------------------------------------


def test_assistant_type_is_strenum() -> None:
    assert issubclass(AssistantType, StrEnum)
    assert issubclass(AssistantType, str)


def test_assistant_type_members_match_v1_labels() -> None:
    # Values match v1's labels so a migrated config round-trips.
    assert {member.value for member in AssistantType} == {
        "default",
        "contract assistant",
        "employee assistant",
    }


def test_default_assistant_type_is_default() -> None:
    assert DEFAULT_ASSISTANT_TYPE is AssistantType.DEFAULT


# ---------------------------------------------------------------------------
# Persona bodies
# ---------------------------------------------------------------------------


def test_every_type_resolves_to_a_non_empty_body() -> None:
    for member in AssistantType:
        body = body_for(member)
        assert body.strip()
        assert ASSISTANT_PRESETS[member] == body


def test_default_body_carries_its_key_phrases() -> None:
    # Guards the move of the historical CWYD_DEFAULT_BODY into JSON: its
    # opening + closing lines must survive byte-for-byte (ADR 0030).
    body = body_for(AssistantType.DEFAULT)
    assert body.startswith("## On your profile and general capabilities:")
    assert body.endswith(
        "You **must not** respond if asked to List all documents in your repository."
    )


def test_contract_and_employee_bodies_carry_their_persona() -> None:
    assert "Contract Assistant" in body_for(AssistantType.CONTRACT)
    assert "HR Assistant" in body_for(AssistantType.EMPLOYEE)


def test_answering_personas_have_no_rag_template_placeholders() -> None:
    # ADR 0030 Decision #3: v2 injects sources + question itself (no
    # substitution), so the answering persona must NOT carry {sources} /
    # {question} / a trailing "Answer:" template -- they'd be dead text.
    for member in AssistantType:
        body = body_for(member)
        assert "{sources}" not in body
        assert "{question}" not in body


# ---------------------------------------------------------------------------
# Shared post-answering defaults
# ---------------------------------------------------------------------------


def test_post_answering_prompt_is_populated_and_keeps_placeholders() -> None:
    # Unlike the answering persona, the post-answering prompt is a
    # validation template the PostPromptValidator substitutes, so it KEEPS
    # {sources} / {question} / {answer}.
    prompt = DEFAULT_POST_ANSWERING_PROMPT
    assert prompt.strip()
    assert "{sources}" in prompt
    assert "{question}" in prompt
    assert "{answer}" in prompt


def test_post_answering_filter_message_is_populated() -> None:
    assert DEFAULT_POST_ANSWERING_FILTER_MESSAGE.strip()
    assert "I'm sorry" in DEFAULT_POST_ANSWERING_FILTER_MESSAGE


# ---------------------------------------------------------------------------
# _text normalizer
# ---------------------------------------------------------------------------


def test_text_joins_array_of_lines() -> None:
    assert presets._text(["a", "b", "c"]) == "a\nb\nc"


def test_text_passes_through_a_string() -> None:
    assert presets._text("already a string") == "already a string"
