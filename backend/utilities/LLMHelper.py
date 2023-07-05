import os
import openai
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from dotenv import load_dotenv

class LLMHelper:
    def __init__(self):
        os.environ["OPENAI_API_BASE"] = f"https://{os.getenv('AZURE_OPENAI_RESOURCE')}.openai.azure.com/"
        os.environ["OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_KEY")
        os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")
        
        # Configure OpenAI API
        openai.api_type = "azure"
        openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        openai.api_base = os.getenv('OPENAI_API_BASE')
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        self.llm = AzureChatOpenAI(deployment_name=os.getenv("AZURE_OPENAI_MODEL"), temperature=0, max_tokens=os.getenv('AZURE_OPENAI_MAX_TOKENS', None), openai_api_version=openai.api_version)
        self.embedding_model = OpenAIEmbeddings(model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL"), chunk_size=1)
        
    def get_llm(self):
        return self.llm
        
    def get_embedding_model(self):
        return self.embedding_model
    
    






