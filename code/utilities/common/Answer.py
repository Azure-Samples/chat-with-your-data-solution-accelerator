import json
from typing import List, Optional
from .SourceDocument import SourceDocument

class Answer:
    def __init__(self, question: str, answer: str, source_documents: List[SourceDocument] = [], prompt_tokens: Optional[int] = 0, completion_tokens: Optional[int] = 0):
        self.question = question
        self.answer = answer
        self.source_documents = source_documents
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        
    def to_json(self):
        return json.dumps(self, cls=AnswerEncoder)
    
    @classmethod
    def from_json(cls, json_string):
        return json.loads(json_string, cls=AnswerDecoder)

class AnswerEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Answer):
            return {
                'question': obj.question,
                'answer': obj.answer,
                'source_documents': [doc.to_json() for doc in obj.source_documents],
                'prompt_tokens': obj.prompt_tokens,
                'completion_tokens': obj.completion_tokens
            }
        return super().default(obj)
    
class AnswerDecoder(json.JSONDecoder):
    def decode(self, s, **kwargs):
        obj = super().decode(s, **kwargs)
        return Answer(
            question=obj['question'],
            answer=obj['answer'],
            source_documents=[SourceDocument.from_json(doc) for doc in obj['source_documents']],
            prompt_tokens=obj['prompt_tokens'],
            completion_tokens=obj['completion_tokens']
        )
    