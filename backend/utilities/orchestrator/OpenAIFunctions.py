from typing import List

from backend.utilities.tools.QuestionAnswerTool import QuestionAnswerTool
from .OrchestratorBase import OrchestratorBase
from ..LLMHelper import LLMHelper
from ..parser.OutputParserTool import OutputParserTool

class OpenAIFunctionsOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.system_message = {"role": "system", "content": "You help employees to navigate only private information sources. You must prioritize the function call over your general knowledge for any question by calling the search_documents function."}
        self.functions = [
            {
                "name": "search_documents",
                "description": "Provide answers to any fact question coming from users.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The message the user sent",
                        },
                    },
                    "required": ["question"],
                },
            },
        ]
        
    def orchestrate(self, question: str, chat_history: List[dict], **kwargs: dict) -> dict:
        
        # Call Content Safety tool
        
        
        # Call function to determine route
        llm_helper = LLMHelper()
        messages = [self.system_message, {"role": "user", "content": question}]
        llm_helper.get_chat_completion(messages, self.functions, function_call="auto")

        # if question
        
        #    run answering chain
        answering_tool = QuestionAnswerTool()
        answer = answering_tool.answer_question(question, chat_history)
        
     
        #    run post prompt if needed
        
        
        # call content safety
        
        
        
        output_formatter = OutputParserTool()
        messages = output_formatter.parse(question=answer.question, answer=answer.answer, source_documents=answer.source_documents)
        
        return messages
        
        

    