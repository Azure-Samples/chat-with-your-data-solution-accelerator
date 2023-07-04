import os
import openai
import logging
import re
import json
from azuresearch import AzureSearch
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain.chains.llm import LLMChain
from langchain.chains.chat_vector_db.prompts import CONDENSE_QUESTION_PROMPT
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback
from opencensus.ext.azure.log_exporter import AzureLogHandler

from .azuresearch import AzureSearch
from .ConfigHelper import ConfigHelper
from .azureblobstorage import AzureBlobStorageClient


# Setting logging
load_dotenv()
logger = logging.getLogger(__name__)
instrumentation_key = (
    f"InstrumentationKey={os.getenv('APPINSIGHTS_INSTRUMENTATIONKEY')}"
)
logger.addHandler(AzureLogHandler(connection_string=instrumentation_key))
logger.setLevel(logging.INFO)

class QuestionHandler:
    def __init__(self):
        load_dotenv()
                
        os.environ["OPENAI_API_BASE"] = f"https://{os.getenv('AZURE_OPENAI_RESOURCE')}.openai.azure.com/"
        os.environ["OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_KEY")
        os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")

        # Configure OpenAI API
        openai.api_type = "azure"
        openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        openai.api_base = os.getenv('OPENAI_API_BASE')
        openai.api_key = os.getenv("OPENAI_API_KEY")

        self.llm = AzureChatOpenAI(deployment_name=os.getenv("AZURE_OPENAI_MODEL"), temperature=0, max_tokens=1000, openai_api_version=openai.api_version)
        self.embeddings = OpenAIEmbeddings(model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL"), chunk_size=1)

        # Connect to search
        self.vector_store = AzureSearch(
                azure_cognitive_search_name=os.getenv('AZURE_SEARCH_SERVICE'),
                azure_cognitive_search_key=os.getenv('AZURE_SEARCH_KEY'),
                index_name=os.getenv('AZURE_SEARCH_INDEX'),
                embedding_function=self.embeddings.embed_query
            )
        self.blob_client = AzureBlobStorageClient()

    def get_answer_using_langchain(self, question, chat_history):
        config = ConfigHelper.get_active_config_or_default()    
        condense_question_prompt = PromptTemplate(template=config.prompts.condense_question_prompt, input_variables=["question", "chat_history"])
        answering_prompt = PromptTemplate(template=config.prompts.answering_prompt, input_variables=["summaries", "question"])
        
        question_generator = LLMChain(
            llm=self.llm, prompt=condense_question_prompt, verbose=True
        )
        doc_chain = load_qa_with_sources_chain(
            self.llm, chain_type="stuff", verbose=True, prompt=answering_prompt
        )
        chain = ConversationalRetrievalChain(
            retriever=self.vector_store.as_retriever(),
            question_generator=question_generator,
            combine_docs_chain=doc_chain,
            return_source_documents=True,
            return_generated_question=True,
        )

        with get_openai_callback() as cb:
            result = chain({"question": question, "chat_history": chat_history})

        properties = {
            "custom_dimensions": {
                "question": question,
                "chatHistory": chat_history,
                "generatedQuestion": result["generated_question"],
                "sourceDocuments": list(map(lambda x: x.metadata, result["source_documents"])),
                "totalTokens": cb.total_tokens,
                "promptTokens": cb.prompt_tokens,
                "completionTokens": cb.completion_tokens,
            }
        }
        logger.info(f"ConversationalRetrievalChain", extra=properties)

        container_sas = self.blob_client.get_container_sas()
                
        answer = result['answer'].replace('  ', ' ')
        source_urls = re.findall(r'\[\[(.*?)\]\]', answer)
        for idx, url in enumerate(source_urls):
            answer = answer.replace(f'[[{url}]]', f'[doc{idx+1}]')

        messages = [
            {
                "role": "tool",
                "content": {"citations": [], "intent": result["generated_question"]},
                "end_turn": False,
            },
            {"role": "assistant", "content": answer, "end_turn": True},
        ]
        
        for url in source_urls:
            # Check which result['source_documents'][x].metadata['source'] matches the url
            for doc in result["source_documents"]:
                if doc.metadata['source'] == url:
                    idx = doc.metadata['chunk']
                    break
            doc = result["source_documents"][idx]
            
            messages[0]["content"]["citations"].append(
                {
                    "content": doc.page_content,
                    "id": idx,
                    "chunk_id": doc.metadata["chunk"],
                    "title": doc.metadata["filename"],
                    "filepath": doc.metadata["filename"],
                    "url": doc.metadata["source"].replace(
                        "_SAS_TOKEN_PLACEHOLDER_", container_sas
                    ),
                    "metadata": doc.metadata,
                })

        # everything in content needs to be stringified to work with Azure BYOD frontend
        messages[0]["content"] = json.dumps(messages[0]["content"])
        return messages


    def handle_question(self, question, chat_history):
        result = self.get_answer_using_langchain(question, chat_history)
        return result
