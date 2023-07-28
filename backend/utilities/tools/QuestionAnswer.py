from typing import List
from .ToolBase import ToolBase

from azuresearch import AzureSearch
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from dotenv import load_dotenv
from langchain.chains.llm import LLMChain
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback
from opencensus.ext.azure.log_exporter import AzureLogHandler

from ..azuresearch import AzureSearch
from ..ConfigHelper import ConfigHelper
from ..LLMHelper import LLMHelper
from ..EnvHelper import EnvHelper


class QuestionAnswerTool(ToolBase):
    def __init__(self) -> None:
        self.name = "QuestionAnswer"
    
    def action(self, input: dict, **kwargs: dict) -> dict:        
        question = input["question"]
        chat_history = input["chat_history"]
        
        config = ConfigHelper.get_active_config_or_default()    
        condense_question_prompt = PromptTemplate(template=config.prompts.condense_question_prompt, input_variables=["question", "chat_history"])
        answering_prompt = PromptTemplate(template=config.prompts.answering_prompt, input_variables=["question", "sources"])
        
        llm_helper = LLMHelper()
        env_helper = EnvHelper()

        question_generator = LLMChain(llm=llm_helper.get_llm(), prompt=condense_question_prompt, verbose=True) 
        
        doc_chain = load_qa_with_sources_chain(
            llm=llm_helper.get_llm(), 
            chain_type="stuff", 
            prompt=answering_prompt,
            document_variable_name="sources",
            verbose=True            
        )
        
        # Connect to search
        self.vector_store = AzureSearch(
                azure_cognitive_search_name= env_helper.AZURE_SEARCH_SERVICE,
                azure_cognitive_search_key= env_helper.AZURE_SEARCH_KEY,
                index_name= env_helper.AZURE_SEARCH_INDEX,
                embedding_function=llm_helper.get_embedding_model().embed_query,
            )
        
        chain = ConversationalRetrievalChain(
            retriever=self.vector_store.as_retriever(),
            question_generator=question_generator,
            combine_docs_chain=doc_chain,
            return_source_documents=True,
            return_generated_question=True
        )
        
        with get_openai_callback() as cb:
            result = chain({"question": question, "chat_history": chat_history})
        
        return result
    