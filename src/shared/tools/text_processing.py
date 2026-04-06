"""Text processing tool: translate, summarize, paraphrase."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.common.answer import Answer
from shared.llm.llm_helper import get_current_date_suffix

if TYPE_CHECKING:
    from shared.llm.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


class TextProcessingTool:
    """Handles text transformation tasks: translate, summarize, paraphrase."""

    def __init__(self, llm_helper: LLMHelper) -> None:
        self.llm_helper = llm_helper

    def answer_question(
        self,
        question: str,
        chat_history: list[dict] | None = None,
        **kwargs,
    ) -> Answer:
        text = kwargs.get("text")
        operation = kwargs.get("operation")

        if text and operation:
            user_content = f"{operation} the following TEXT: {text}"
        else:
            user_content = question

        system_message = "You are an AI assistant for the user." + get_current_date_suffix()
        response = self.llm_helper.get_chat_completion(
            [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ]
        )

        return Answer(
            question=question,
            answer=response.choices[0].message.content or "",
            source_documents=[],
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )
