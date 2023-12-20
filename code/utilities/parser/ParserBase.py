# Create an abstract class for parser
from abc import ABC, abstractmethod
from typing import List
from ..common.SourceDocument import SourceDocument


class ParserBase(ABC):
    """
    Base class for parsers.
    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    def parse(self, question: str, answer: str, source_documents: List[SourceDocument], **kwargs: dict) -> List[dict]:
        """
        Parses the given question and answer using the provided source documents.

        Args:
            question (str): The question to be parsed.
            answer (str): The answer to be parsed.
            source_documents (List[SourceDocument]): The list of source documents to be used for parsing.
            **kwargs (dict): Additional keyword arguments.

        Returns:
            List[dict]: A list of parsed results in the form of dictionaries.
        """
        pass
