from typing import List
from ..helpers.LLMHelper import LLMHelper
from .AnsweringToolBase import AnsweringToolBase
from ..common.Answer import Answer


class TextProcessingTool(AnsweringToolBase):
    """
    A tool for processing text and generating answers using a language model.

    Attributes:
        name (str): The name of the tool.
    """

    def __init__(self) -> None:
        self.name = "TextProcessing"

    def answer_question(self, question: str, chat_history: List[dict], **kwargs: dict):
        """
        Generates an answer to a given question using a language model.

        Args:
            question (str): The question to be answered.
            chat_history (List[dict]): The chat history as a list of dictionaries.
            **kwargs (dict): Additional keyword arguments.

        Returns:
            Answer: The generated answer.
        """

        llm_helper = LLMHelper()
        text = kwargs.get('text')
        operation = kwargs.get('operation')
        user_content = f"{operation} the following TEXT: {text}" if question == "" else question

        system_message = """You are an AI assistant for the user."""

        result = llm_helper.get_chat_completion(
            [{"role": "system", "content": system_message},
             {"role": "user", "content": user_content},]
        )

        answer = Answer(question=question,
                        answer=result['choices'][0]['message']['content'],
                        source_documents=[],
                        prompt_tokens=result['usage']['prompt_tokens'],
                        completion_tokens=result['usage']['completion_tokens'])
        return answer
