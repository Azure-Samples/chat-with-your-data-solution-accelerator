from typing import Annotated

from semantic_kernel.functions import kernel_function

from ..common.Answer import Answer
from ..tools.QuestionAnswerTool import QuestionAnswerTool
from ..tools.TextProcessingTool import TextProcessingTool


class ChatPlugin:
    def __init__(self, question: str, chat_history: list[dict]) -> None:
        self.question = question
        self.chat_history = chat_history

    @kernel_function(
        description="Provide answers to any fact question coming from users."
    )
    def search_documents(
        self,
        question: Annotated[
            str, "A standalone question, converted from the chat history"
        ],
    ) -> Answer:
        # TODO: Use Semantic Kernel to call LLM
        return QuestionAnswerTool().answer_question(
            question=question, chat_history=self.chat_history
        )

    @kernel_function(
        description="Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on."
    )
    def text_processing(
        self,
        text: Annotated[str, "The text to be processed"],
        operation: Annotated[
            str,
            "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc. If a language is specified, return that as part of the operation. Preserve the operation name in the user language.",
        ],
    ) -> Answer:
        # TODO: Use Semantic Kernel to call LLM
        return TextProcessingTool().answer_question(
            question=self.question,
            chat_history=self.chat_history,
            text=text,
            operation=operation,
        )
