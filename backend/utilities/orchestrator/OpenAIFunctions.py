from typing import List, Optional
import json

from .OrchestratorBase import OrchestratorBase
from ..helpers.LLMHelper import LLMHelper
from ..helpers.ConfigHelper import ConfigHelper
from ..tools.PostPromptTool import PostPromptTool
from ..tools.QuestionAnswerTool import QuestionAnswerTool
from ..tools.TextProcessingTool import TextProcessingTool
from ..tools.ContentSafetyChecker import ContentSafetyChecker
from ..parser.OutputParserTool import OutputParserTool
from ..common.Answer import Answer

class OpenAIFunctionsOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()   
        self.content_safety_checker = ContentSafetyChecker()
        self.functions = [
            {
                "name": "search_documents",
                "description": "Provide answers to any fact question coming from users.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "A standalone question, converted from the chat history",
                        },
                    },
                    "required": ["question"],
                },
            },
            {
                "name": "text_processing",
                "description": "Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to be processed",
                        },
                        "operation": {
                            "type": "string",
                            "description": "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc. If a language is specified, return that as part of the operation. Preserve the operation name in the user language.",
                        },
                    },
                    "required": ["text", "operation"],
                },
            }
        ]
        
    def orchestrate(self, user_message: str, chat_history: List[dict], **kwargs: dict) -> dict:
        output_formatter = OutputParserTool()
        
        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            filtered_user_message = self.content_safety_checker.validate_input_and_replace_if_harmful(user_message)
            if user_message != filtered_user_message:
                messages = output_formatter.parse(question=user_message, answer=filtered_user_message, source_documents=[])
                return messages
        
        # Call function to determine route
        llm_helper = LLMHelper()

        system_message = """You help employees to navigate only private information sources.
        You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
        Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
        When directly replying to the user, always reply in the language the user is speaking.
        """
        # Create conversation history
        messages = [{"role": "system", "content": system_message}]        
        for message in chat_history:
            messages.append({"role": "user", "content": message[0]})
            messages.append({"role": "assistant", "content": message[1]})
        messages.append({"role": "user", "content": user_message})
        
        result = llm_helper.get_chat_completion_with_functions(messages, self.functions, function_call="auto")      
        self.log_tokens(prompt_tokens=result.usage.prompt_tokens, completion_tokens=result.usage.completion_tokens)
        
        # TODO: call content safety if needed
                        
        if result.choices[0].finish_reason == "function_call":
            if result.choices[0].message.function_call.name == "search_documents":
                question = json.loads(result.choices[0].message.function_call.arguments)['question']
                # run answering chain
                answering_tool = QuestionAnswerTool()
                answer = answering_tool.answer_question(question, chat_history)

                self.log_tokens(prompt_tokens=answer.prompt_tokens, completion_tokens=answer.completion_tokens)

                # Run post prompt if needed
                if self.config.prompts.enable_post_answering_prompt:
                    post_prompt_tool = PostPromptTool()
                    answer = post_prompt_tool.validate_answer(answer)
                    self.log_tokens(prompt_tokens=answer.prompt_tokens, completion_tokens=answer.completion_tokens)                
            elif result.choices[0].message.function_call.name == "text_processing":
                text = json.loads(result.choices[0].message.function_call.arguments)['text']
                operation = json.loads(result.choices[0].message.function_call.arguments)['operation']
                text_processing_tool = TextProcessingTool()
                answer = text_processing_tool.answer_question(user_message, chat_history, text=text, operation=operation)
                self.log_tokens(prompt_tokens=answer.prompt_tokens, completion_tokens=answer.completion_tokens)
        else:
            text = result.choices[0].message.content
            answer = Answer(question=user_message, answer=text)

        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            filtered_answer = self.content_safety_checker.validate_output_and_replace_if_harmful(answer.answer)
            if answer.answer != filtered_answer:
                messages = output_formatter.parse(question=user_message, answer=filtered_answer, source_documents=[])
                return messages
        
        # Format the output for the UI        
        messages = output_formatter.parse(question=answer.question, answer=answer.answer, source_documents=answer.source_documents)
        return messages
        