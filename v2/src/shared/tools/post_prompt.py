"""Post-answering validator (groundedness check).

Pillar: Stable Core
Phase: 3

Mirrors the v1 `PostPromptTool` intent: after the LLM produces an
answer, ask the LLM a second time whether the answer is grounded in
the retrieved sources. If not, swap the answer for a configurable
filter message.

v2 differences vs v1:
- LLM is dependency-injected (any `BaseLLMProvider`) -- no helper
  singletons, no `ConfigHelper` reach-around.
- Validation prompt and filter message are constructor parameters,
  not pulled from a global config object.
- Async-only.
- Operates on typed inputs (`SearchResult`) and returns a typed
  result -- no `Answer` god-object.

NOT a registry domain (per development_plan.md task #20). Tools are
imported directly:

    from shared.tools.post_prompt import PostPromptValidator
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel

from shared.types import ChatMessage, SearchResult

if TYPE_CHECKING:
    from shared.providers.llm.base import BaseLLMProvider


# Default validation prompt -- asks the model for a single yes/no token
# so the parse step stays trivial. Format placeholders match the v1
# contract (`{question}`, `{answer}`, `{sources}`) so existing prompt
# overrides drop in unchanged.
DEFAULT_VALIDATION_PROMPT = (
    "You are validating an assistant answer for groundedness.\n\n"
    "QUESTION:\n{question}\n\n"
    "ANSWER:\n{answer}\n\n"
    "SOURCES:\n{sources}\n\n"
    "Is the ANSWER fully supported by the SOURCES? Reply with a single "
    "word: 'true' if grounded, 'false' otherwise."
)

DEFAULT_FILTER_MESSAGE = (
    "I'm sorry, I can't provide a grounded answer to that question "
    "based on the available sources."
)

# Tokens the model may return for an affirmative groundedness verdict.
# Lower-cased before comparison; punctuation/whitespace stripped.
_GROUNDED_TOKENS = frozenset({"true", "yes", "grounded", "supported"})


class ValidationResult(BaseModel):
    """Outcome of a `PostPromptValidator.validate()` call."""

    grounded: bool
    answer: str


class PostPromptValidator:
    def __init__(
        self,
        llm: "BaseLLMProvider",
        *,
        validation_prompt: str = DEFAULT_VALIDATION_PROMPT,
        filter_message: str = DEFAULT_FILTER_MESSAGE,
    ) -> None:
        self._llm = llm
        self._validation_prompt = validation_prompt
        self._filter_message = filter_message

    @staticmethod
    def _format_sources(sources: Sequence[SearchResult]) -> str:
        # Mirrors v1's `[docN]: <content>` shape so the same validation
        # prompt template works without rewriting.
        if not sources:
            return ""
        return "\n".join(
            f"[doc{i + 1}]: {src.content}" for i, src in enumerate(sources)
        )

    async def validate(
        self,
        question: str,
        answer: str,
        sources: Sequence[SearchResult],
        *,
        deployment: str | None = None,
    ) -> ValidationResult:
        """Verify `answer` is grounded in `sources`.

        Empty / whitespace-only answer short-circuits to `grounded=False`
        with the filter message -- no point in burning a model call.
        Returns the original answer when grounded, the filter message
        otherwise.
        """
        if not answer or not answer.strip():
            return ValidationResult(grounded=False, answer=self._filter_message)

        prompt = self._validation_prompt.format(
            question=question,
            answer=answer,
            sources=self._format_sources(sources),
        )
        reply = await self._llm.chat(
            [ChatMessage(role="user", content=prompt)],
            deployment=deployment,
        )
        verdict = reply.content.strip().strip(".").lower()
        grounded = verdict in _GROUNDED_TOKENS
        return ValidationResult(
            grounded=grounded,
            answer=answer if grounded else self._filter_message,
        )
