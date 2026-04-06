"""LLM helper: wraps Azure OpenAI chat models, embeddings, and raw client."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from openai import AzureOpenAI

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion

    from shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)


def get_current_date_suffix() -> str:
    """Date context appended to system prompts — matches old CWYD behaviour."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return (
        "\nYou must only provide numerical dates in your answers using the format "
        "YYYY-MM-DD unless explicitly asked to use a different format. "
        f"Today's date is {today}."
    )


class LLMHelper:
    """Provides configured chat models, embeddings, and raw OpenAI client."""

    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings
        oai = settings.openai
        auth = settings.auth

        # Raw AzureOpenAI client for direct API calls
        client_kwargs: dict = {
            "azure_endpoint": oai.endpoint,
            "api_version": oai.api_version,
        }
        if auth.azure_auth_type == "keys":
            client_kwargs["api_key"] = oai.api_key
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), auth.azure_token_provider_scope
            )
            client_kwargs["azure_ad_token_provider"] = token_provider
            self._token_provider = token_provider

        self.openai_client = AzureOpenAI(**client_kwargs)

    # ── LangChain models ─────────────────────────────────────────────

    def get_chat_model(self) -> AzureChatOpenAI:
        oai = self.settings.openai
        kwargs: dict = {
            "azure_deployment": oai.model,
            "temperature": oai.temperature,
            "max_tokens": oai.max_tokens or None,
            "openai_api_version": oai.api_version,
            "azure_endpoint": oai.endpoint,
        }
        if self.settings.auth.azure_auth_type == "keys":
            kwargs["api_key"] = oai.api_key
        else:
            kwargs["azure_ad_token_provider"] = self._token_provider
        return AzureChatOpenAI(**kwargs)

    def get_embeddings_model(self) -> AzureOpenAIEmbeddings:
        oai = self.settings.openai
        search = self.settings.search
        supports_dims = "text-embedding-3" in oai.embedding_model.lower()
        dims = search.dimensions if supports_dims and search.dimensions else None
        kwargs: dict = {
            "azure_endpoint": oai.endpoint,
            "azure_deployment": oai.embedding_model,
            "model": oai.embedding_model,
            "chunk_size": 1,
        }
        if dims is not None:
            kwargs["dimensions"] = dims
        if self.settings.auth.azure_auth_type == "keys":
            kwargs["api_key"] = oai.api_key
        else:
            kwargs["azure_ad_token_provider"] = self._token_provider
        return AzureOpenAIEmbeddings(**kwargs)

    # ── Raw OpenAI client calls ──────────────────────────────────────

    def generate_embeddings(self, text_or_tokens: str | list[int]) -> list[float]:
        """Generate embeddings via the raw OpenAI client. Accepts text or token array."""
        oai = self.settings.openai
        kwargs: dict = {"input": [text_or_tokens], "model": oai.embedding_model}
        supports_dims = "text-embedding-3" in oai.embedding_model.lower()
        if supports_dims and self.settings.search.dimensions:
            kwargs["dimensions"] = self.settings.search.dimensions
        return self.openai_client.embeddings.create(**kwargs).data[0].embedding

    def get_chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        **kwargs,
    ) -> ChatCompletion:
        return self.openai_client.chat.completions.create(
            model=model or self.settings.openai.model,
            messages=messages,
            max_tokens=self.settings.openai.max_tokens or None,
            **kwargs,
        )

    def get_chat_completion_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> ChatCompletion:
        """Chat completion with tool calling (modern replacement for functions param)."""
        return self.openai_client.chat.completions.create(
            model=self.settings.openai.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )

    # ── Semantic Kernel integration ──────────────────────────────

    def get_sk_chat_completion_service(self, service_id: str):
        """Return a Semantic Kernel AzureChatCompletion service instance."""
        from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

        oai = self.settings.openai
        kwargs: dict = {
            "service_id": service_id,
            "deployment_name": oai.model,
            "endpoint": oai.endpoint,
            "api_version": oai.api_version,
        }
        if self.settings.auth.azure_auth_type == "keys":
            kwargs["api_key"] = oai.api_key
        else:
            kwargs["ad_token_provider"] = self._token_provider
        return AzureChatCompletion(**kwargs)

    def get_sk_service_settings(self, service):
        """Return Semantic Kernel prompt execution settings."""
        from typing import cast

        from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
            AzureChatPromptExecutionSettings,
        )

        oai = self.settings.openai
        return cast(
            AzureChatPromptExecutionSettings,
            service.instantiate_prompt_execution_settings(
                service_id=service.service_id,
                temperature=0,
                max_tokens=oai.max_tokens or None,
            ),
        )
