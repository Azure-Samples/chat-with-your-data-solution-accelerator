from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.helpers.llm_helper import LLMHelper
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from openai.types.embedding import Embedding


AZURE_OPENAI_ENDPOINT = "https://mock-endpoint"
AZURE_OPENAI_API_VERSION = "mock-api-version"
OPENAI_API_KEY = "mock-api-key"
AZURE_OPENAI_MODEL = "mock-model"
AZURE_OPENAI_MAX_TOKENS = "100"
AZURE_OPENAI_EMBEDDING_MODEL = "mock-embedding-model"
AZURE_SUBSCRIPTION_ID = "mock-subscription-id"
AZURE_RESOURCE_GROUP = "mock-resource-group"
AZURE_ML_WORKSPACE_NAME = "mock-ml-workspace"
PROMPT_FLOW_ENDPOINT_NAME = "mock-endpoint-name"
PROMPT_FLOW_DEPLOYMENT_NAME = "mock-deployment-name"


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.helpers.llm_helper.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.is_auth_type_keys.return_value = True
        env_helper.AZURE_OPENAI_ENDPOINT = AZURE_OPENAI_ENDPOINT
        env_helper.AZURE_OPENAI_API_VERSION = AZURE_OPENAI_API_VERSION
        env_helper.OPENAI_API_KEY = OPENAI_API_KEY
        env_helper.AZURE_OPENAI_MODEL = AZURE_OPENAI_MODEL
        env_helper.AZURE_OPENAI_MAX_TOKENS = AZURE_OPENAI_MAX_TOKENS
        env_helper.AZURE_OPENAI_EMBEDDING_MODEL = AZURE_OPENAI_EMBEDDING_MODEL
        env_helper.AZURE_SUBSCRIPTION_ID = AZURE_SUBSCRIPTION_ID
        env_helper.AZURE_RESOURCE_GROUP = AZURE_RESOURCE_GROUP
        env_helper.AZURE_ML_WORKSPACE_NAME = AZURE_ML_WORKSPACE_NAME
        env_helper.PROMPT_FLOW_ENDPOINT_NAME = PROMPT_FLOW_ENDPOINT_NAME
        env_helper.PROMPT_FLOW_DEPLOYMENT_NAME = PROMPT_FLOW_DEPLOYMENT_NAME

        yield env_helper


@pytest.fixture(autouse=True)
def azure_openai_mock():
    with patch("backend.batch.utilities.helpers.llm_helper.AzureOpenAI") as mock:
        yield mock


@patch("backend.batch.utilities.helpers.llm_helper.AzureChatCompletion")
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


@patch("backend.batch.utilities.helpers.llm_helper.AzureChatCompletion")
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


def test_generate_embeddings_embeds_input(azure_openai_mock):
    # given
    llm_helper = LLMHelper()

    # when
    llm_helper.generate_embeddings("some input")

    # then
    azure_openai_mock.return_value.embeddings.create.assert_called_once_with(
        input=["some input"], model=AZURE_OPENAI_EMBEDDING_MODEL
    )


def test_generate_embeddings_returns_embeddings(azure_openai_mock):
    # given
    llm_helper = LLMHelper()
    expected_embeddings = [1, 2, 3]
    azure_openai_mock.return_value.embeddings.create.return_value = (
        CreateEmbeddingResponse(
            data=[
                Embedding(embedding=expected_embeddings, index=0, object="embedding")
            ],
            model="mock-model",
            object="list",
            usage={"prompt_tokens": 0, "total_tokens": 0},
        )
    )

    # when
    actual_embeddings = llm_helper.generate_embeddings("some input")

    # then
    assert actual_embeddings == expected_embeddings


@patch("backend.batch.utilities.helpers.llm_helper.DefaultAzureCredential")
@patch("backend.batch.utilities.helpers.llm_helper.MLClient")
def test_get_ml_client_initializes_with_expected_parameters(
    mock_ml_client, mock_default_credential, env_helper_mock
):
    # given
    llm_helper = LLMHelper()

    # when
    llm_helper.get_ml_client()

    # then
    mock_ml_client.assert_called_once_with(
        mock_default_credential.return_value,
        env_helper_mock.AZURE_SUBSCRIPTION_ID,
        env_helper_mock.AZURE_RESOURCE_GROUP,
        env_helper_mock.AZURE_ML_WORKSPACE_NAME,
    )
