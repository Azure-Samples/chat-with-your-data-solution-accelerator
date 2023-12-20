# Create an abstract class for tool
from abc import ABC, abstractmethod

from ..common.Answer import Answer


class AnswerProcessingBase(ABC):
    """
    Base class for processing answers.
    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    def process_answer(self, answer: Answer, **kwargs: dict) -> Answer:
        """
        Abstract method for processing an answer.

        Parameters:
        - answer (Answer): The answer to be processed.
        - kwargs (dict): Additional keyword arguments.

        Returns:
        - Answer: The processed answer.
        """
        pass
