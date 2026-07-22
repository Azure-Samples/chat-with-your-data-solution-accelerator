"""Loads the assistant-type prompt presets from ``assistant_presets.json`` (sibling
file) once at import and exposes typed accessors. The JSON holds the
operator-editable persona bodies (one per :class:`AssistantType`) plus the
shared post-answering defaults; the fixed ``CWYD_GUARDRAIL`` is appended at
runtime in :mod:`backend.core.agents.definitions` and is deliberately NOT in the
data file (non-negotiable safety stays in code).

Prompt bodies are authored as arrays of lines in the JSON for readability and
joined with ``\\n`` here. The ``default`` persona is the single source of the
historical ``CWYD_DEFAULT_BODY``; ``definitions.py`` re-exports it from here.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_PRESETS_PATH = Path(__file__).with_name("assistant_presets.json")


class AssistantType(StrEnum):
    """The selectable answering-prompt personas (ADR 0030, Hard Rule #11).

    Values match v1's labels so a migrated config round-trips. Selecting a
    type loads its body into ``cwyd_agent_instructions``; the fixed guardrail
    still wraps it at runtime via ``resolve_cwyd_instructions``.
    """

    DEFAULT = "default"
    CONTRACT = "contract assistant"
    EMPLOYEE = "employee assistant"


class _PresetsFile(BaseModel):
    """Parsed shape of ``assistant_presets.json`` (ADR 0030).

    ``extra="ignore"`` tolerates the leading ``_comment`` field. Each prompt
    value is authored either as an array of lines (joined with ``\\n``) or a
    plain string; :func:`_text` normalizes both.
    """

    model_config = ConfigDict(extra="ignore")

    default_assistant_type: str
    assistant_types: dict[str, list[str] | str]
    post_answering_prompt: list[str] | str
    post_answering_filter_message: list[str] | str


def _text(value: list[str] | str) -> str:
    """Normalize a JSON prompt value (array of lines OR a string) to text.

    Multi-line prompts are authored as arrays of lines (joined with ``\\n``);
    single-line values (the filter message) may be a plain string.
    """
    if isinstance(value, list):
        return "\n".join(value)
    return value


def _load() -> _PresetsFile:
    """Read + validate the presets JSON (loud on any malformation)."""
    with _PRESETS_PATH.open(encoding="utf-8") as handle:
        return _PresetsFile.model_validate_json(handle.read())


_FILE = _load()

#: ``{AssistantType: persona body}`` for every selectable type (guardrail-free).
ASSISTANT_PRESETS: dict[AssistantType, str] = {
    member: _text(_FILE.assistant_types[member.value]) for member in AssistantType
}

#: The type selected when no override is saved (matches v1's initial config).
DEFAULT_ASSISTANT_TYPE = AssistantType(_FILE.default_assistant_type)

#: Shared post-answering validation prompt default. KEEPS its
#: ``{sources}`` / ``{question}`` / ``{answer}`` placeholders -- the
#: ``PostPromptValidator`` substitutes them (unlike the answering persona).
DEFAULT_POST_ANSWERING_PROMPT = _text(_FILE.post_answering_prompt)

#: Shared message returned to the user when the post-answering check fails.
DEFAULT_POST_ANSWERING_FILTER_MESSAGE = _text(_FILE.post_answering_filter_message)


def body_for(assistant_type: AssistantType) -> str:
    """Return the guardrail-free persona body for ``assistant_type``."""
    return ASSISTANT_PRESETS[assistant_type]
