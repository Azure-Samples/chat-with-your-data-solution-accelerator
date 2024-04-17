from openai import AzureOpenAI
from typing import List
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from .EnvHelper import EnvHelper


class LLMHelper:
    def __init__(self):
        self.env_helper: EnvHelper = EnvHelper()
        self.auth_type = self.env_helper.AZURE_AUTH_TYPE
        self.token_provider = self.env_helper.AZURE_TOKEN_PROVIDER

        if self.auth_type == "rbac":
            self.openai_client = AzureOpenAI(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                azure_ad_token_provider=self.token_provider,
            )
        else:
            self.openai_client = AzureOpenAI(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                api_key=self.env_helper.OPENAI_API_KEY,
            )

        self.llm_model = self.env_helper.AZURE_OPENAI_MODEL
        self.llm_max_tokens = (
            self.env_helper.AZURE_OPENAI_MAX_TOKENS
            if self.env_helper.AZURE_OPENAI_MAX_TOKENS != ""
            else None
        )
        self.embedding_model = self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL

    def get_llm(self):
        if self.auth_type == "rbac":
            return AzureChatOpenAI(
                deployment_name=self.llm_model,
                temperature=0,
                max_tokens=self.llm_max_tokens,
                openai_api_version=self.openai_client._api_version,
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                azure_ad_token_provider=self.token_provider,
            )
        else:
            return AzureChatOpenAI(
                deployment_name=self.llm_model,
                temperature=0,
                max_tokens=self.llm_max_tokens,
                openai_api_version=self.openai_client._api_version,
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_key=self.env_helper.OPENAI_API_KEY,
            )

    # TODO: This needs to have a custom callback to stream back to the UI
    def get_streaming_llm(self):
        if self.auth_type == "rbac":
            return AzureChatOpenAI(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_key=self.env_helper.OPENAI_API_KEY,
                streaming=True,
                callbacks=[StreamingStdOutCallbackHandler],
                deployment_name=self.llm_model,
                temperature=0,
                max_tokens=self.llm_max_tokens,
                openai_api_version=self.openai_client._api_version,
                azure_ad_token_provider=self.token_provider,
            )
        else:
            return AzureChatOpenAI(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_key=self.env_helper.OPENAI_API_KEY,
                streaming=True,
                callbacks=[StreamingStdOutCallbackHandler],
                deployment_name=self.llm_model,
                temperature=0,
                max_tokens=self.llm_max_tokens,
                openai_api_version=self.openai_client._api_version,
            )

    def get_embedding_model(self):
        if self.auth_type == "rbac":
            return AzureOpenAIEmbeddings(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                azure_deployment=self.embedding_model,
                chunk_size=1,
                azure_ad_token_provider=self.token_provider,
            )
        else:
            return AzureOpenAIEmbeddings(
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                api_key=self.env_helper.OPENAI_API_KEY,
                azure_deployment=self.embedding_model,
                chunk_size=1,
            )

    def get_chat_completion_with_functions(
        self, messages: List[dict], functions: List[dict], function_call: str = "auto"
    ):
        return self.openai_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            functions=functions,
            function_call=function_call,
        )

    def get_chat_completion(self, messages: List[dict]):
        return self.openai_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
        )
