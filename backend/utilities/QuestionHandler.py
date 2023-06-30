import os
import openai
from azuresearch import AzureSearch
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain.chains.llm import LLMChain
from langchain.chains.chat_vector_db.prompts import CONDENSE_QUESTION_PROMPT
from langchain.chains import ConversationalRetrievalChain


class QuestionHandler:
    def __init__(self):
        load_dotenv()
        
        os.environ["OPENAI_API_BASE"] = f"https://{os.getenv('AZURE_OPENAI_RESOURCE')}.openai.azure.com/"

        # Configure OpenAI API
        openai.api_type = "azure"
        openai.api_version = os.getenv("AZURE_OPENAI_PREVIEW_API_VERSION")
        openai.api_base = os.getenv('OPENAI_API_BASE')
        openai.api_key = os.getenv("OPENAI_API_KEY")

        self.llm = AzureChatOpenAI(deployment_name=os.getenv("AZURE_OPENAI_MODEL"), temperature=0, openai_api_version=openai.api_version)
        self.embeddings = OpenAIEmbeddings(model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL"), chunk_size=1)

        # Connect to search
        self.vector_store = AzureSearch(
                azure_cognitive_search_name=os.getenv('AZURE_SEARCH_SERVICE'),
                azure_cognitive_search_key=os.getenv('AZURE_SEARCH_KEY'),
                index_name=os.getenv('AZURE_SEARCH_INDEX'),
                embedding_function=self.embeddings.embed_query
            )

        self.question_generator = LLMChain(llm=self.llm, prompt=CONDENSE_QUESTION_PROMPT, verbose=True)
        self.doc_chain = load_qa_with_sources_chain(self.llm, chain_type="stuff", verbose=True)
        self.chain = ConversationalRetrievalChain(
            retriever=self.vector_store.as_retriever(),
            question_generator=self.question_generator,
            combine_docs_chain=self.doc_chain,
            return_source_documents=True
        )

    def handle_question(self, question, chat_history):
        result = self.chain({"question": question, "chat_history": chat_history})
        return result
