from .AnsweringToolBase import AnsweringToolBase

from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback
from opencensus.ext.azure.log_exporter import AzureLogHandler

from ..ConfigHelper import ConfigHelper

class PostPromptTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "PostPrompt"
    
    def action(self, input: dict, **kwargs: dict) -> dict:        
        result = input["result"]
        answer = result['answer']
        
        config = ConfigHelper.get_active_config_or_default()    
    
        was_message_filtered = False
        if config.prompts.enable_post_answering_prompt:
            post_answering_prompt = PromptTemplate(template=config.prompts.post_answering_prompt, input_variables=["question", "answer", "sources"])
            post_answering_chain = LLMChain(llm=self.llm, prompt=post_answering_prompt, output_key="correct", verbose=True)
            # Filter sources to only include used ones            
            sources = [f"{doc.metadata['source']}: {doc.page_content}" for doc in result['source_documents'] if doc.metadata['source'] in answer]
            sources = '\n'.join(sources)      
     
            with get_openai_callback() as cb:
                post_result = post_answering_chain({"question": result["generated_question"], "answer": answer, "sources": sources})
            
            was_message_filtered = not (post_result['correct'].lower() == 'true' or post_result['correct'].lower() == 'yes')

        # Replace answer with filtered message
        if was_message_filtered:
            answer = config.messages.post_answering_filter
    
        return answer
    