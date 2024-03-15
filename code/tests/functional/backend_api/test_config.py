import json
import pytest
import requests

from tests.functional.backend_api.app_config import AppConfig

pytestmark = pytest.mark.functional


def test_config_returned(app_url: str, app_config: AppConfig):
    # when
    response = requests.get(f"{app_url}/api/config")

    # then
    assert response.status_code == 200
    assert json.loads(response.text) == {
        "azureSpeechKey": app_config.get("AZURE_SPEECH_SERVICE_KEY"),
        "azureSpeechRegion": app_config.get("AZURE_SPEECH_SERVICE_REGION"),
        "OPENAI_API_BASE": app_config.get("OPENAI_API_BASE"),
    }
    assert response.headers["Content-Type"] == "application/json"
