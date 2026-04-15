"""Post-prompt validation tool: fact-checks the answer against sources."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.common.answer import Answer

if TYPE_CHECKING:
    from shared.config.models import ConfigModel
    from shared.llm.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


class PostPromptTool:
    """Validates answers using a post-answering prompt.

    The LLM is asked whether the answer is grounded in the sources.
    If it responds "true" or "yes", the answer passes; otherwise it
    is replaced with a filter message.
    """

    def __init__(self, llm_helper: LLMHelper, config: ConfigModel) -> None:
        self.llm_helper = llm_helper
        self.config = config

    def validate_answer(self, answer: Answer) -> Answer:
        prompts = self.config.prompts
        if not prompts.enable_post_answering_prompt:
            return answer

        sources = "\n".join(
            f"[doc{i + 1}]: {doc.content}"
            for i, doc in enumerate(answer.source_documents)
        )
        prompt = (prompts.post_answering_prompt or "").format(
            question=answer.question, answer=answer.answer, sources=sources
        )

        response = self.llm_helper.get_chat_completion(
            [{"role": "user", "content": prompt}]
        )
        result = (response.choices[0].message.content or "").strip().lower()
        usage = response.usage

        if result in ("true", "yes"):
            return Answer(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )

        filter_msg = self.config.messages.post_answering_filter if self.config.messages else ""
        return Answer(
            question=answer.question,
            answer=filter_msg or "The answer was filtered by the post-answering validation.",
            source_documents=[],
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
