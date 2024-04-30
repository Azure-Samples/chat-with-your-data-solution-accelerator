from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.helpers.LLMHelper import LLMHelper
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

AZURE_OPENAI_ENDPOINT = "https://mock-endpoint"
AZURE_OPENAI_API_VERSION = "mock-api-version"
OPENAI_API_KEY = "mock-api-key"
AZURE_OPENAI_MODEL = "mock-model"
AZURE_OPENAI_MAX_TOKENS = "100"
AZURE_OPENAI_EMBEDDING_MODEL = "mock-embedding-model"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.helpers.LLMHelper.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.is_auth_type_keys.return_value = True
        env_helper.AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT
        env_helper.AZURE_OPENAI_API_VERSION = AZURE_OPENAI_API_VERSION
        env_helper.OPENAI_API_KEY = OPENAI_API_KEY
        env_helper.AZURE_OPENAI_MODEL = AZURE_OPENAI_MODEL
        env_helper.AZURE_OPENAI_MAX_TOKENS = AZURE_OPENAI_MAX_TOKENS
        env_helper.AZURE_OPENAI_EMBEDDING_MODEL = AZURE_OPENAI_EMBEDDING_MODEL

        yield env_helper


@patch("backend.batch.utilities.helpers.LLMHelper.AzureChatCompletion")
def test_get_sk_chat_completion_service_keys(AzureChatCompletionMock: MagicMock):
    # given
    llm_helper = LLMHelper()

    # when
    llm_helper.get_sk_chat_completion_service("service-id")

    # then
    AzureChatCompletionMock.assert_called_once_with(
        service_id="service-id",
        deployment_name=AZURE_OPENAI_MODEL,
        endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        api_key=OPENAI_API_KEY,
    )


@patch("backend.batch.utilities.helpers.LLMHelper.AzureChatCompletion")
def test_get_sk_chat_completion_service_rbac(
    AzureChatCompletionMock: MagicMock, env_helper_mock: MagicMock
):
    # given
    env_helper_mock.is_auth_type_keys.return_value = False
    llm_helper = LLMHelper()

    # when
    llm_helper.get_sk_chat_completion_service("service-id")

    # then
    AzureChatCompletionMock.assert_called_once_with(
        service_id="service-id",
        deployment_name=AZURE_OPENAI_MODEL,
        endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        ad_token_provider=env_helper_mock.AZURE_TOKEN_PROVIDER,
    )


def test_get_sk_service_settings():
    # given
    llm_helper = LLMHelper()
    service = AzureChatCompletion(
        deployment_name="mock-deployment",
        endpoint="https://mock-endpoint",
        api_key="mock-api-key",
        service_id="mock-service-id",
    )

    # when
    settings = llm_helper.get_sk_service_settings(service)

    # then
    assert settings.service_id == "mock-service-id"
    assert settings.temperature == 0
    assert settings.max_tokens == int(AZURE_OPENAI_MAX_TOKENS)
