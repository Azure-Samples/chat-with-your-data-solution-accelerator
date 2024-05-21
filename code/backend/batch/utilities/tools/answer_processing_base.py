# Create an abstract class for tool
from abc import ABC, abstractmethod
from ..common.answer import Answer


class AnswerProcessingBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def process_answer(self, answer: Answer, **kwargs: dict) -> Answer:
        pass
