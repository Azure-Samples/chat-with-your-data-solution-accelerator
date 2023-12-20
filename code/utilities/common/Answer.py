import json
from typing import List, Optional
from .SourceDocument import SourceDocument


class Answer:
    """
    Represents an answer to a question.

    Attributes:
        question (str): The question that was asked.
        answer (str): The answer to the question.
        source_documents (List[SourceDocument]): The list of source documents used to generate the answer.
        prompt_tokens (Optional[int]): The number of tokens in the prompt used to generate the answer.
        completion_tokens (Optional[int]): The number of tokens in the completed answer.
    """

    def __init__(self, question: str, answer: str, source_documents: List[SourceDocument] = [], prompt_tokens: Optional[int] = 0, completion_tokens: Optional[int] = 0):
        self.question = question
        self.answer = answer
        self.source_documents = source_documents
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def to_json(self):
        """
        Convert the Answer object to a JSON string.

        Returns:
            str: The JSON representation of the Answer object.
        """
        return json.dumps(self, cls=AnswerEncoder)

    @classmethod
    def from_json(cls, json_string):
        return json.loads(json_string, cls=AnswerDecoder)


class AnswerEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for serializing Answer objects.

    This encoder is used to convert Answer objects into JSON format.
    It overrides the default() method of the JSONEncoder class to handle
    serialization of Answer objects.

    Attributes:
        None

    Methods:
        default(obj): Overrides the default() method of JSONEncoder to handle
                      serialization of Answer objects.

    Usage:
        Use this class to encode Answer objects into JSON format.
        Pass an instance of this class as the `cls` parameter when calling
        the json.dumps() function.
    """

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
    """
    Custom JSON decoder for decoding Answer objects from JSON strings.
    """

    def decode(self, s, **kwargs):
        """
        Decode a JSON string into an Answer object.

        Args:
            s (str): The JSON string to decode.
            **kwargs: Additional keyword arguments.

        Returns:
            Answer: The decoded Answer object.
        """
        obj = super().decode(s, **kwargs)
        return Answer(
            question=obj['question'],
            answer=obj['answer'],
            source_documents=[SourceDocument.from_json(
                doc) for doc in obj['source_documents']],
            prompt_tokens=obj['prompt_tokens'],
            completion_tokens=obj['completion_tokens']
        )
