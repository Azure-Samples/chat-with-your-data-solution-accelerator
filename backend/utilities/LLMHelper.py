import openai
from typing import List
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from .EnvHelper import EnvHelper

class LLMHelper:
    def __init__(self):
        env_helper: EnvHelper = EnvHelper()

        # Configure OpenAI API
        openai.api_type = "azure"
        openai.api_version = env_helper.AZURE_OPENAI_API_VERSION
        openai.api_base = env_helper.OPENAI_API_BASE
        openai.api_key = env_helper.OPENAI_API_KEY
        
        self.llm_model = env_helper.AZURE_OPENAI_MODEL
        self.llm_max_tokens = env_helper.AZURE_OPENAI_MAX_TOKENS if env_helper.AZURE_OPENAI_MAX_TOKENS != '' else None
        self.embedding_model = env_helper.AZURE_OPENAI_EMBEDDING_MODEL
                
    def get_llm(self):
        return AzureChatOpenAI(deployment_name=self.llm_model, temperature=0, max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)
    
    # TODO: This needs to have a custom callback to stream back to the UI
    def get_streaming_llm(self):
        return AzureChatOpenAI(streaming=True, callbacks=[StreamingStdOutCallbackHandler], deployment_name=self.llm_model, temperature=0, 
                               max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)
    
    def get_embedding_model(self):
        return OpenAIEmbeddings(deployment_id=self.embedding_model, chunk_size=1)
    
    def get_chat_completion_with_functions(self, messages: List[dict], functions: List[dict], function_call: str="auto"):
        return openai.ChatCompletion.create(
            deployment_id=self.llm_model,
            messages=messages,
            functions=functions,
            function_call=function_call,
            )
        
    def get_chat_completion(self, messages: List[dict]):
        return openai.ChatCompletion.create(
            deployment_id=self.llm_model,
            messages=messages,
            )
