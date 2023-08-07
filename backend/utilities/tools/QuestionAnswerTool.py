from typing import List
from .AnsweringToolBase import AnsweringToolBase

from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from dotenv import load_dotenv
from langchain.chains.llm import LLMChain
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback
from opencensus.ext.azure.log_exporter import AzureLogHandler

from ..AzureSearchHelper import AzureSearchHelper
from ..ConfigHelper import ConfigHelper
from ..LLMHelper import LLMHelper
from ..EnvHelper import EnvHelper
from .Answer import Answer
from ..parser.SourceDocument import SourceDocument

class QuestionAnswerTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "QuestionAnswer"
        self.vector_store = AzureSearchHelper().get_vector_store()
        self.verbose = True
    
    def answer_question(self, question: str, chat_history: List[dict], **kwargs: dict):
        config = ConfigHelper.get_active_config_or_default()    
        # condense_question_prompt = PromptTemplate(template=config.prompts.condense_question_prompt, input_variables=["question", "chat_history"])
        answering_prompt = PromptTemplate(template=config.prompts.answering_prompt, input_variables=["question", "sources"])
        
        llm_helper = LLMHelper()
        env_helper = EnvHelper()

        # Run answering chain
        # question_generator = LLMChain(llm=llm_helper.get_llm(), prompt=condense_question_prompt, verbose=self.verbose) 
        # result = question_generator({"question": question, "chat_history": chat_history})
        # # print("Question generator:", result)
        # generated_question = result["text"]
        # print(f"{question} --> {generated_question}")
        
        # Retrieve documents as sources
        sources = self.vector_store.similarity_search(query=question, k=4, search_type="hybrid")
        # print("Sources:", sources)
        
        # Generate answer from sources
        answer_generator = LLMChain(llm=llm_helper.get_llm(), prompt=answering_prompt, verbose=self.verbose)
        sources_text = "\n\n".join([f"[doc{i+1}]: {source.page_content}" for i, source in enumerate(sources)])
                
        result = answer_generator({"question": question, "sources": sources_text})
        # print("Answer chain:", result)
        answer = result["text"]
        print(f"Answer: {answer}")
        # with get_openai_callback() as cb:
        #     result = chain({"question": question, "chat_history": chat_history})
        
        # Generate Answer Object
        source_documents = []
        for source in sources:
            source_document = SourceDocument(
                id=source.metadata["id"],
                content=source.page_content,
                title=source.metadata["title"],
                source=source.metadata["source"],
                chunk=source.metadata["chunk"],
                offset=source.metadata["offset"],
                page_number=source.metadata["page_number"],
            )
            source_documents.append(source_document)
        
        clean_answer = Answer(question=question,
                              answer=answer,
                              source_documents=source_documents)
        
        return clean_answer
    