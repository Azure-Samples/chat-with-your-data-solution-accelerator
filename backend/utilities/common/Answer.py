from typing import List, Optional
from .SourceDocument import SourceDocument

class Answer:
    def __init__(self, question: str, answer: str, source_documents: List[SourceDocument] = [], prompt_tokens: Optional[int] = 0, completion_tokens: Optional[int] = 0):
        self.question = question
        self.answer = answer
        self.source_documents = source_documents
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
    