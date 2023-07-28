from typing import Optional, List
from .OrchestratorBase import OrchestratorBase
from ..LLMHelper import LLMHelper

class OpenAIFunctionsOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
    
    def orchestrate(self, question: str, functions: List[dict], system_message: Optional[dict], **kwargs: dict) -> dict:        
        llm_helper = LLMHelper()
        # Define the functions to use
        system_message = system_message if system_message else {"role": "system", "content": "You help employees to navigate only private information sources. You must prioritize the function call over your general knowledge for any question by calling the search_documents function."}
        messages = [system_message, {"role": "user", "content": question}]
        llm_helper = LLMHelper()
        # TO DO: Implement conversion to dict
        return llm_helper.get_chat_completion(messages, functions, function_call = "auto")
    