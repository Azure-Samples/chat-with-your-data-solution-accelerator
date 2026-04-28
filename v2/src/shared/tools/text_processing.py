"""Text processing helper.

Pillar: Stable Core
Phase: 3

Light wrapper that runs an arbitrary text operation (summarize,
translate, rewrite, ...) through the configured LLM provider. Mirrors
the v1 `TextProcessingTool` intent (operation + text → answer) but
without the v1 baggage:

- LLM is dependency-injected (any `BaseLLMProvider`); no SDK or
  helper singletons.
- Async-only -- the chat pipeline (task #22) and orchestrators
  consume it from an async context.
- Returns plain text -- citation/wrapping is the caller's job
  (task #23 owns `Citation` extraction).

NOT a registry domain (per development_plan.md task #20). Tools are
imported directly:

    from shared.tools.text_processing import TextProcessingHelper
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from shared.types import ChatMessage

if TYPE_CHECKING:
    from shared.providers.llm.base import BaseLLMProvider


DEFAULT_SYSTEM_PROMPT = (
    "You are a concise, accurate text-processing assistant. Apply the "
    "requested operation to the provided text and return only the "
    "transformed text -- no commentary, no preamble."
)


class TextProcessingHelper:
    def __init__(
        self,
        llm: "BaseLLMProvider",
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._llm = llm
        self._system_prompt = system_prompt

    async def process(
        self,
        text: str,
        operation: str,
        *,
        deployment: str | None = None,
    ) -> str:
        """Run `operation` against `text` via the LLM.

        - `operation`: free-form natural-language instruction
          ("Summarize", "Translate to French", "Rewrite as bullet
          points", ...). The caller controls the verb -- this helper
          does not constrain the vocabulary.
        - `text`: input payload. Empty / whitespace-only short-circuits
          to "" so callers don't burn a model call on an idle prompt.
        - `deployment`: pass-through to the LLM provider; None uses
          the provider's default chat deployment.
        """
        if not operation or not operation.strip():
            raise ValueError("operation must be a non-empty string")
        if not text or not text.strip():
            return ""

        user_content = f"{operation.strip()} the following TEXT:\n\n{text}"
        messages = [
            ChatMessage(role="system", content=self._system_prompt),
            ChatMessage(role="user", content=user_content),
        ]
        reply = await self._llm.chat(messages, deployment=deployment)
        return reply.content
