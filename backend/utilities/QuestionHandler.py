import os
import openai
import logging
import re
import json
from azuresearch import AzureSearch
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from dotenv import load_dotenv
from langchain.chains.llm import LLMChain
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback
from opencensus.ext.azure.log_exporter import AzureLogHandler

from .azuresearch import AzureSearch
from .ConfigHelper import ConfigHelper
from .LLMHelper import LLMHelper
from .azureblobstorage import AzureBlobStorageClient
from .EnvHelper import EnvHelper


# Setting logging
load_dotenv()
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string=os.getenv('APPINSIGHTS_CONNECTION_STRING')))
logger.setLevel(logging.INFO)

class QuestionHandler:
    def __init__(self):
        env_helper : EnvHelper = EnvHelper()

        self.llm = LLMHelper().get_llm()
        self.embeddings = LLMHelper().get_embedding_model()

        # Connect to search
        self.vector_store = AzureSearch(
                azure_cognitive_search_name= env_helper.AZURE_SEARCH_SERVICE,
                azure_cognitive_search_key= env_helper.AZURE_SEARCH_KEY,
                index_name= env_helper.AZURE_SEARCH_INDEX,
                embedding_function=self.embeddings.embed_query
            )
        self.blob_client = AzureBlobStorageClient()

    def get_answer_using_langchain(self, question, chat_history):
        config = ConfigHelper.get_active_config_or_default()    
        condense_question_prompt = PromptTemplate(template=config.prompts.condense_question_prompt, input_variables=["question", "chat_history"])
        answering_prompt = PromptTemplate(template=config.prompts.answering_prompt, input_variables=["question", "sources"])
        
        question_generator = LLMChain(
            llm=self.llm, prompt=condense_question_prompt, verbose=True
        )
       
        doc_chain = load_qa_with_sources_chain(
            self.llm, 
            chain_type="stuff", 
            prompt=answering_prompt,
            document_variable_name="sources",
            verbose=True            
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

        answer = result['answer'].replace('  ', ' ')

        was_message_filtered = False
        post_total_tokens, post_prompt_tokens, post_completion_tokens = 0, 0, 0
        if config.prompts.enable_post_answering_prompt:
            post_answering_prompt = PromptTemplate(template=config.prompts.post_answering_prompt, input_variables=["question", "answer", "sources"])
            post_answering_chain = LLMChain(llm=self.llm, prompt=post_answering_prompt, output_key="correct", verbose=True)
            # Filter sources to only include used ones            
            sources = [f"{doc.metadata['source']}: {doc.page_content}" for doc in result['source_documents'] if doc.metadata['source'] in answer]
            sources = '\n'.join(sources)      
     
            with get_openai_callback() as cb_post:
                post_result = post_answering_chain({"question": result["generated_question"], "answer": answer, "sources": sources})
            
            post_total_tokens, post_prompt_tokens, post_completion_tokens = cb_post.total_tokens, cb_post.prompt_tokens, cb_post.completion_tokens
            was_message_filtered = not (post_result['correct'].lower() == 'true' or post_result['correct'].lower() == 'yes')

        # Setting log properties
        log_properties = {
            "custom_dimensions": {
            }
        }
        if config.logging.log_tokens:
            tokens_properties = {
                "totalTokens": cb.total_tokens + post_total_tokens,
                "promptTokens": cb.prompt_tokens + post_prompt_tokens,
                "completionTokens": cb.completion_tokens + post_completion_tokens,
            } 
            log_properties['custom_dimensions'].update(tokens_properties)
            
        if config.logging.log_user_interactions:
            user_interactions_properties = {
                "userQuestion": question,
                "userChatHistory": chat_history,
                "generatedQuestion": result["generated_question"],
                "sourceDocuments": list(map(lambda x: json.dumps(x.metadata), result["source_documents"])),
                "messageFiltered": was_message_filtered
            }
            log_properties['custom_dimensions'].update(user_interactions_properties)
        
        logger.info(f"ConversationalRetrievalChain", extra=log_properties)

        # Replace answer with filtered message
        if was_message_filtered:
            answer = config.messages.post_answering_filter

        # Replace [[url]] with [docx] for citation feature to work
        source_urls = re.findall(r'\[\[(.*?)\]\]', answer)
        for idx, url in enumerate(source_urls):
            answer = answer.replace(f'[[{url}]]', f'[doc{idx+1}]')

        # create return message object
        messages = [
            {
                "role": "tool",
                "content": {"citations": [], "intent": result["generated_question"]},
                "end_turn": False,
            }
        ]
        
        container_sas = self.blob_client.get_container_sas()
        for url_idx, url in enumerate(source_urls):
            # Check which result['source_documents'][x].metadata['source'] matches the url
            idx = None
            try:
                idx = [doc.metadata['source'] for doc in result["source_documents"]].index(url)
            except ValueError:
                logging.info('Could not find source document for url: ' + url)
            if idx is not None:
                doc = result["source_documents"][idx]
            
                # Then update the citation object in the response, it needs to have filepath and chunk_id to render in the UI as a file
                messages[0]["content"]["citations"].append(
                    {
                        "content": doc.metadata["markdown_url"].replace(
                            "_SAS_TOKEN_PLACEHOLDER_", container_sas
                        ) + "\n\n\n" + doc.page_content,
                        "id": url_idx,
                        "chunk_id": doc.metadata["chunk"],
                        "title": doc.metadata["filename"], # we need to use original_filename as LangChain needs filename-chunk as unique identifier
                        "filepath": doc.metadata["filename"],
                        "url": doc.metadata["markdown_url"].replace(
                            "_SAS_TOKEN_PLACEHOLDER_", container_sas
                        ),
                        "metadata": doc.metadata,
                    })
        if messages[0]["content"]["citations"] == []:
            answer = re.sub(r'\[doc\d+\]', '', answer)
        messages.append({"role": "assistant", "content": answer, "end_turn": True})
                # everything in content needs to be stringified to work with Azure BYOD frontend
        messages[0]["content"] = json.dumps(messages[0]["content"])
        return messages


    def handle_question(self, question, chat_history):
        result = self.get_answer_using_langchain(question, chat_history)
        return result
