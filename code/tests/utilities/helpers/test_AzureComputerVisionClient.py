import json
from unittest import mock
from unittest.mock import MagicMock
import pytest
from pytest_httpserver import HTTPServer

from backend.batch.utilities.helpers.AzureComputerVisionClient import (
    AzureComputerVisionClient,
)
from tests.request_matching import RequestMatcher, verify_request_made


IMAGE_URL = "some-image-url.jpg"
VECTORIZE_IMAGE_PATH = "/computervision/retrieval:vectorizeImage"
REQUEST_METHOD = "POST"
AZURE_COMPUTER_VISION_KEY = "some-api-key"


@pytest.fixture
def env_helper_mock(httpserver: HTTPServer):
    env_helper_mock = MagicMock()
    env_helper_mock.AZURE_COMPUTER_VISION_ENDPOINT = httpserver.url_for("")
    env_helper_mock.AZURE_COMPUTER_VISION_KEY = AZURE_COMPUTER_VISION_KEY
    env_helper_mock.is_auth_type_keys.return_value = True
    return env_helper_mock


@pytest.fixture
def azure_computer_vision_client(env_helper_mock: MagicMock):
    return AzureComputerVisionClient(env_helper_mock)


@pytest.fixture
def azure_computer_vision_client_rbac(env_helper_mock: MagicMock):
    env_helper_mock.is_auth_type_keys.return_value = False
    return AzureComputerVisionClient(env_helper_mock)


def test_vectorize_image_calls_computer_vision_with_key_based_authentication(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_json(
        {"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]}
    )

    # when
    azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    verify_request_made(
        httpserver,
        RequestMatcher(
            path=VECTORIZE_IMAGE_PATH,
            method=REQUEST_METHOD,
            query_string="api-version=2024-02-01&model-version=2023-04-15",
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": AZURE_COMPUTER_VISION_KEY,
            },
            json={"url": IMAGE_URL},
        ),
    )


def test_vectorize_image_calls_computer_vision_with_rbac_based_authentication(
    httpserver: HTTPServer, azure_computer_vision_client_rbac: AzureComputerVisionClient
):
    # given
    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_json(
        {"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]}
    )

    # when
    with mock.patch(
        "backend.batch.utilities.helpers.AzureComputerVisionClient.DefaultAzureCredential"
    ) as mock_default_azure_credential:
        with mock.patch(
            "backend.batch.utilities.helpers.AzureComputerVisionClient.get_bearer_token_provider"
        ) as mock_get_bearer_token_provider:
            mock_get_bearer_token_provider.return_value.return_value = "dummy token"

            azure_computer_vision_client_rbac.vectorize_image(IMAGE_URL)

            # then
            mock_default_azure_credential.assert_called_once()
            mock_get_bearer_token_provider.assert_called_once_with(
                mock_default_azure_credential.return_value,
                "https://cognitiveservices.azure.com/.default",
            )

            verify_request_made(
                httpserver,
                RequestMatcher(
                    path=VECTORIZE_IMAGE_PATH,
                    method=REQUEST_METHOD,
                    query_string="api-version=2024-02-01&model-version=2023-04-15",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer dummy token",
                    },
                    json={"url": IMAGE_URL},
                ),
            )


def test_returns_image_vectors(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    expected_vectors = [1.0, 2.0, 3.0]

    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_json(
        {"modelVersion": "2022-04-11", "vector": expected_vectors}
    )

    # when
    actual_vectors = azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert actual_vectors == expected_vectors


def test_raises_exception_if_bad_response_code(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = {"error": "computer says no"}
    response_status = 500
    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_json(
        response_body, status=response_status
    )

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to vectorize image failed with status: {response_status} body: {json.dumps(response_body, indent=4)}"
    )


def test_raises_exception_if_non_json_response(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = "not json"
    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_data(
        response_body, status=200
    )

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to vectorize image returned malformed response body: {response_body}"
    )


def test_raises_exception_if_vector_not_in_response(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = {"modelVersion": "2022-04-11"}
    httpserver.expect_request(VECTORIZE_IMAGE_PATH, REQUEST_METHOD).respond_with_json(
        response_body, status=200
    )

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to vectorize image returned no vector: {response_body}"
    )
