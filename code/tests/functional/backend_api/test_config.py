import json
from unittest.mock import patch
from backend.auth.token_validator import TokenValidator
import pytest
import requests

from tests.functional.backend_api.app_config import AppConfig

pytestmark = pytest.mark.functional


def test_config_returned(app_url: str, app_config: AppConfig):
    # when
    with patch.object(TokenValidator, 'validate', return_value=None):
        response = requests.get(f"{app_url}/api/config", headers={"Authorization": "Bearer valid_token"})

    # then
    assert response.status_code == 200
    assert json.loads(response.text) == {
        "AZURE_OPENAI_ENDPOINT": app_config.get("AZURE_OPENAI_ENDPOINT"),
        "azureSpeechKey": app_config.get("AZURE_SPEECH_SERVICE_KEY"),
        "azureSpeechRegion": app_config.get("AZURE_SPEECH_SERVICE_REGION"),
    }
    assert response.headers["Content-Type"] == "application/json"
