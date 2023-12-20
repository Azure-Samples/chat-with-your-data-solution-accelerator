import openai
from typing import List
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from .EnvHelper import EnvHelper


class LLMHelper:
    """
    Helper class for interacting with the Language Model (LLM).
    """

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
        """
        Get an instance of AzureChatOpenAI for Language Model (LLM) interaction.

        Returns:
            AzureChatOpenAI: An instance of AzureChatOpenAI.
        """
        return AzureChatOpenAI(deployment_name=self.llm_model, temperature=0, max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)

    def get_streaming_llm(self):
        """
        Get an instance of AzureChatOpenAI for streaming Language Model (LLM) interaction.

        Returns:
            AzureChatOpenAI: An instance of AzureChatOpenAI with streaming enabled.
        """
        return AzureChatOpenAI(streaming=True, callbacks=[StreamingStdOutCallbackHandler], deployment_name=self.llm_model, temperature=0,
                               max_tokens=self.llm_max_tokens, openai_api_version=openai.api_version)

    def get_embedding_model(self):
        """
        Get an instance of OpenAIEmbeddings for embedding model interaction.

        Returns:
            OpenAIEmbeddings: An instance of OpenAIEmbeddings.
        """
        return OpenAIEmbeddings(deployment=self.embedding_model, chunk_size=1)

    def get_chat_completion_with_functions(self, messages: List[dict], functions: List[dict], function_call: str = "auto"):
        """
        Get chat completion with custom functions.

        Args:
            messages (List[dict]): List of messages in the conversation.
            functions (List[dict]): List of custom functions to be used.
            function_call (str, optional): Function call type. Defaults to "auto".

        Returns:
            ChatCompletion: A chat completion response.
        """
        return openai.ChatCompletion.create(
            deployment_id=self.llm_model,
            messages=messages,
            functions=functions,
            function_call=function_call,
        )

    def get_chat_completion(self, messages: List[dict]):
        """
        Get chat completion.

        Args:
            messages (List[dict]): List of messages in the conversation.

        Returns:
            ChatCompletion: A chat completion response.
        """
        return openai.ChatCompletion.create(
            deployment_id=self.llm_model,
            messages=messages,
        )
