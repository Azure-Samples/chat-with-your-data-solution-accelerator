from typing import List
from ..parser.SourceDocument import SourceDocument

class Answer:
    def __init__(self, question: str, answer: str, source_documents: List[SourceDocument]):
        self.question = question
        self.answer = answer
        self.source_documents = source_documents