# Create an abstract class for tool
from abc import ABC, abstractmethod
from typing import List
from ..common.answer import Answer


class AnsweringToolBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def answer_question(
        self, question: str, chat_history: List[dict], **kwargs
    ) -> Answer:
        pass
