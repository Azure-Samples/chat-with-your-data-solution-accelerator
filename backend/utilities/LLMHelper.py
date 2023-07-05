import os
import openai
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

class LLMHelper:
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
        
        self.llm_model = os.getenv("AZURE_OPENAI_MODEL")
        self.llm_max_tokens = os.getenv('AZURE_OPENAI_MAX_TOKENS', None)
        self.embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")
                
    def get_llm(self):
        return AzureChatOpenAI(deployment_name=self.llm_model, temperature=0, max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)
    
    # TODO: This needs to have a custom callback to stream back to the UI
    def get_streaming_llm(self):
        return AzureChatOpenAI(streaming=True, callbacks=[StreamingStdOutCallbackHandler], deployment_name=self.llm_model, temperature=0, 
                               max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)
    
    def get_embedding_model(self):
        return OpenAIEmbeddings(model=self.embedding_model, chunk_size=1)
    
    