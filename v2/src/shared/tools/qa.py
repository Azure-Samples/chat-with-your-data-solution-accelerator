"""Question-answering helper (RAG composition).

Pillar: Stable Core
Phase: 3

Composes a `BaseSearch` retriever and a `BaseLLMProvider` into a single
async `answer()` call: query -> retrieve -> prompt -> answer + cited
sources.

v2 differences vs v1 `QuestionAnswerTool`:
- Search and LLM are dependency-injected (no global helpers, no
  `EnvHelper`/`ConfigHelper` reach-around).
- Async-only.
- Returns a typed `QAResult` -- the answer string plus the
  `SearchResult`s used as context. Citation rendering is the caller's
  job (task #23).
- No image / vision branch and no few-shot example block. Those were
  v1 admin-config features; if Phase 5 brings them back they slot in
  as a subclass override of `_compose_messages()`.

NOT a registry domain (per development_plan.md task #20). Tools are
imported directly:

    from shared.tools.qa import QuestionAnsweringHelper
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel, Field

from shared.types import ChatMessage, SearchResult

if TYPE_CHECKING:
    from shared.providers.llm.base import BaseLLMProvider
    from shared.providers.search.base import BaseSearch


# Default Azure-OpenAI-On-Your-Data-style prompts. The system message
# pins behaviour to the supplied sources; the user template surfaces
# `[docN]:` indices the model can cite. Format placeholders match v1's
# `answering_user_prompt` (`{question}`, `{sources}`) so existing
# overrides drop in unchanged.
DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant that answers questions strictly using the "
    "provided SOURCES. Cite sources inline as [doc1], [doc2], etc. If "
    "the SOURCES do not contain the answer, say you don't know -- do "
    "not invent information."
)

DEFAULT_USER_PROMPT = (
    "SOURCES:\n{sources}\n\n"
    "QUESTION:\n{question}\n\n"
    "Answer the question using only the SOURCES above. Cite each fact "
    "with the matching [docN] tag."
)


class QAResult(BaseModel):
    """Outcome of a `QuestionAnsweringHelper.answer()` call."""

    answer: str
    sources: list[SearchResult] = Field(default_factory=list)


class QuestionAnsweringHelper:
    def __init__(
        self,
        llm: "BaseLLMProvider",
        search: "BaseSearch",
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        user_prompt: str = DEFAULT_USER_PROMPT,
    ) -> None:
        self._llm = llm
        self._search = search
        self._system_prompt = system_prompt
        self._user_prompt = user_prompt

    @staticmethod
    def _format_sources(sources: Sequence[SearchResult]) -> str:
        # Mirror v1's `[docN]: <content>` shape so the model emits
        # citations the frontend can resolve back to a `SearchResult`.
        if not sources:
            return ""
        return "\n\n".join(
            f"[doc{i + 1}]: {src.content}" for i, src in enumerate(sources)
        )

    def _compose_messages(
        self,
        question: str,
        chat_history: Sequence[ChatMessage],
        sources: Sequence[SearchResult],
    ) -> list[ChatMessage]:
        # System prompt first, then prior turns, then the grounded
        # user message. Subclasses can override for vision / few-shot
        # variants without touching `answer()`.
        return [
            ChatMessage(role="system", content=self._system_prompt),
            *chat_history,
            ChatMessage(
                role="user",
                content=self._user_prompt.format(
                    question=question,
                    sources=self._format_sources(sources),
                ),
            ),
        ]

    async def answer(
        self,
        question: str,
        *,
        chat_history: Sequence[ChatMessage] = (),
        top_k: int | None = None,
        deployment: str | None = None,
    ) -> QAResult:
        """Retrieve, prompt, and return a grounded answer.

        Empty / whitespace-only question short-circuits to an empty
        `QAResult` -- no search call, no model call.
        """
        if not question or not question.strip():
            return QAResult(answer="", sources=[])

        sources = list(await self._search.search(question, top_k=top_k))
        messages = self._compose_messages(question, chat_history, sources)
        reply = await self._llm.chat(messages, deployment=deployment)
        return QAResult(answer=reply.content, sources=sources)
