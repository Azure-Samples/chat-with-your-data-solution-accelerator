# Create an abstract class for tool
from abc import ABC, abstractmethod
from typing import List
from ..common.Answer import Answer


class AnsweringToolBase(ABC):
    """
    Base class for answering tools.

    Attributes:
        None

    Methods:
        answer_question: Abstract method to answer a question based on chat history.
    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    def answer_question(self, question: str, chat_history: List[Dict], **kwargs: Dict) -> Answer:
        """
            Answers the given question based on the provided chat history.

            Args:
                question (str): The question to be answered.
                chat_history (List[Dict]): The chat history containing previous messages.
                **kwargs (Dict): Additional keyword arguments.

            Returns:
                Answer: The answer to the question.
            """
        pass
