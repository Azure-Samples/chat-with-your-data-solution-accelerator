import json
import pytest
import requests

pytestmark = pytest.mark.functional


def test_config_returned(app_url: str):
    # when
    response = requests.get(f"{app_url}/api/config")

    # then
    assert response.status_code == 200
    assert json.loads(response.text) == {
        "azureSpeechKey": None,
        "azureSpeechRegion": None,
    }
    assert response.headers["Content-Type"] == "application/json"
