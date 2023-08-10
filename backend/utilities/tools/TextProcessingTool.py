from typing import List
from ..LLMHelper import LLMHelper
from .AnsweringToolBase import AnsweringToolBase
from .Answer import Answer


class TextProcessingTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "TextProcessing"
    
    def answer_question(self, question: str, chat_history: List[dict], **kwargs: dict):
        
        llm_helper = LLMHelper()
        text = kwargs['text']
        operation = kwargs['operation']
        
        system_message = """You are an AI assistant for the user."""

        print(operation, " the following TEXT: ", text)

        result = llm_helper.get_chat_completion(
                   [{"role": "system", "content": system_message}, 
                    {"role": "user", "content": f"{operation} the following TEXT: {text}"}]
                   )
               
        answer = Answer(question=question, 
                        answer=result['choices'][0]['message']['content'], 
                        source_documents=[],
                        prompt_tokens=result['usage']['prompt_tokens'],
                        completion_tokens=result['usage']['completion_tokens'])
        return answer