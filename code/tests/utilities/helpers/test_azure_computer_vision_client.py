import json
from json import JSONDecodeError
from unittest import mock
from unittest.mock import MagicMock
import pytest
from pytest_httpserver import HTTPServer
from trustme import CA
import werkzeug
import time
from requests import ReadTimeout

from backend.batch.utilities.helpers.azure_computer_vision_client import (
    AzureComputerVisionClient,
)
from tests.request_matching import RequestMatcher, verify_request_made
from tests.constants import (
    COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
    COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    COMPUTER_VISION_VECTORIZE_TEXT_PATH,
    COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
)


# These tests utilize `pytest_httpserver` to mock the Azure Computer Vision API. This is instead of mocking the requests
# library directly, like other client classes. The reasons for doing this are:
# 1. This gives us complete confidence that the requests library works as we expect it to, for example parsing of bad
# json.
# 2. It allows us to test the actual HTTP request that is being made to the Azure Computer Vision API.
# 3. If we need to change which http library we are using, there should be minimal changes required to the tests.
#
# If and when the Azure Computer Vision Python SDK starts to support the `vectorizeImage` and `vectorizeText` endpoints,
# and we switch to it, we should consider switching back to convential test mocking.

IMAGE_URL = "some-image-url.jpg"
TEXT = "some text"
AZURE_COMPUTER_VISION_KEY = "some-api-key"


@pytest.fixture(autouse=True)
def pytest_ssl(monkeypatch: pytest.MonkeyPatch, ca: CA):
    with ca.cert_pem.tempfile() as ca_temp_path:
        monkeypatch.setenv("SSL_CERT_FILE", ca_temp_path)
        monkeypatch.setenv("CURL_CA_BUNDLE", ca_temp_path)
        yield


@pytest.fixture
def env_helper_mock(httpserver: HTTPServer):
    env_helper_mock = MagicMock()
    env_helper_mock.AZURE_COMPUTER_VISION_ENDPOINT = httpserver.url_for("")
    env_helper_mock.AZURE_COMPUTER_VISION_KEY = AZURE_COMPUTER_VISION_KEY
    env_helper_mock.AZURE_COMPUTER_VISION_TIMEOUT = 0.25
    env_helper_mock.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION = "2024-02-01"
    env_helper_mock.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION = "2023-04-15"
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
    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]})

    # when
    azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    verify_request_made(
        httpserver,
        RequestMatcher(
            path=COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
            method=COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
            query_string="api-version=2024-02-01&model-version=2023-04-15",
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": AZURE_COMPUTER_VISION_KEY,
            },
            json={"url": IMAGE_URL},
        ),
    )


@mock.patch(
    "backend.batch.utilities.helpers.azure_computer_vision_client.DefaultAzureCredential"
)
@mock.patch(
    "backend.batch.utilities.helpers.azure_computer_vision_client.get_bearer_token_provider"
)
def test_vectorize_image_calls_computer_vision_with_rbac_based_authentication(
    mock_get_bearer_token_provider: MagicMock,
    mock_default_azure_credential: MagicMock,
    httpserver: HTTPServer,
    azure_computer_vision_client_rbac: AzureComputerVisionClient,
):
    # given
    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]})

    # when
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
            path=COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
            method=COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
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

    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": expected_vectors})

    # when
    actual_vectors = azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert actual_vectors == expected_vectors


def test_returns_text_vectors(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    expected_vectors = [3.0, 2.0, 1.0]

    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_TEXT_PATH,
        COMPUTER_VISION_VECTORIZE_TEXT_REQUEST_METHOD,
    ).respond_with_json({"modelVersion": "2022-04-11", "vector": expected_vectors})

    # when
    actual_vectors = azure_computer_vision_client.vectorize_text(TEXT)

    # then
    assert actual_vectors == expected_vectors


def test_vectorize_image_calls_computer_vision_timeout(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    def handler(_) -> werkzeug.Response:
        time.sleep(0.3)
        return werkzeug.Response(
            json.dumps({"modelVersion": "2022-04-11", "vector": [1.0, 2.0, 3.0]}),
            status=200,
        )

    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_handler(handler)

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    assert exec_info.value.args[0] == "Call to Azure Computer Vision failed"
    assert isinstance(exec_info.value.__cause__, ReadTimeout)


def test_raises_exception_if_bad_response_code(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = {"error": "computer says no"}
    response_status = 500
    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json(response_body, status=response_status)

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to Azure Computer Vision failed with status: {response_status}, body: {json.dumps(response_body, indent=4)}"
    )


def test_raises_exception_if_non_json_response(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = "not json"
    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_data(response_body, status=200)

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to Azure Computer Vision returned malformed response body: {response_body}"
    )
    assert isinstance(exec_info.value.__cause__, JSONDecodeError)


def test_raises_exception_if_vector_not_in_response(
    httpserver: HTTPServer, azure_computer_vision_client: AzureComputerVisionClient
):
    # given
    response_body = {"modelVersion": "2022-04-11"}
    httpserver.expect_request(
        COMPUTER_VISION_VECTORIZE_IMAGE_PATH,
        COMPUTER_VISION_VECTORIZE_IMAGE_REQUEST_METHOD,
    ).respond_with_json(response_body, status=200)

    # when
    with pytest.raises(Exception) as exec_info:
        azure_computer_vision_client.vectorize_image(IMAGE_URL)

    # then
    assert (
        exec_info.value.args[0]
        == f"Call to Azure Computer Vision returned no vector: {response_body}"
    )
