import pytest
import requests
from pytest_httpserver import HTTPServer
from tests.functional.app_config import AppConfig
from tests.request_matching import (
    RequestMatcher,
    verify_request_made,
)

pytestmark = pytest.mark.functional


def test_speech_token_returned(app_url: str, app_config: AppConfig):
    # when
    response = requests.get(f"{app_url}/api/speech")

    # then
    assert response.status_code == 200
    assert response.json() == {
        "token": "speech-token",
        "region": app_config.get("AZURE_SPEECH_SERVICE_REGION"),
        "languages": app_config.get("AZURE_SPEECH_RECOGNIZER_LANGUAGES").split(","),
        "key": "some-azure-speech-service-key"
    }
    assert response.headers["Content-Type"] == "application/json"


def test_speech_service_called_correctly(
    app_url: str, app_config: AppConfig, httpserver: HTTPServer
):
    # when
    requests.get(f"{app_url}/api/speech")

    # then
    verify_request_made(
        mock_httpserver=httpserver,
        request_matcher=RequestMatcher(
            path="/sts/v1.0/issueToken",
            method="POST",
            headers={
                "Ocp-Apim-Subscription-Key": app_config.get("AZURE_SPEECH_SERVICE_KEY")
            },
            times=1,
        ),
    )


def test_failure_fetching_speech_token(app_url: str, httpserver: HTTPServer):
    httpserver.expect_oneshot_request(
        "/sts/v1.0/issueToken",
        method="POST",
    ).respond_with_json({"error": "Bad request"}, status=400)

    # when
    response = requests.get(f"{app_url}/api/speech")

    # then
    assert response.status_code == 400
    assert response.json() == {"error": "Failed to get speech config"}
    assert response.headers["Content-Type"] == "application/json"
