from typing import List
from ..helpers.llm_helper import LLMHelper
from .answering_tool_base import AnsweringToolBase
from ..common.answer import Answer


class TextProcessingTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "TextProcessing"

    def answer_question(self, question: str, chat_history: List[dict] = [], **kwargs):
        llm_helper = LLMHelper()
        text = kwargs.get("text")
        operation = kwargs.get("operation")
        user_content = (
            f"{operation} the following TEXT: {text}"
            if (text and operation)
            else question
        )

        system_message = """You are an AI assistant for the user."""

        result = llm_helper.get_chat_completion(
            [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ]
        )

        answer = Answer(
            question=question,
            answer=result.choices[0].message.content,
            source_documents=[],
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
        )
        return answer
