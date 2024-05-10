from unittest.mock import MagicMock, patch
from pytest import MonkeyPatch
from backend.batch.utilities.helpers.env_helper import SecretHelper


def test_get_secret_returns_value_from_environment_variables(monkeypatch: MonkeyPatch):
    # given
    secret_name = "MY_SECRET"
    expected_value = "my_secret_value"
    monkeypatch.setenv(secret_name, expected_value)
    secret_helper = SecretHelper()

    # when
    actual_value = secret_helper.get_secret(secret_name)

    # then
    assert actual_value == expected_value


@patch("backend.batch.utilities.helpers.env_helper.SecretClient")
def test_get_secret_returns_value_from_secret_client_when_use_key_vault_is_true(
    secret_client: MagicMock, monkeypatch: MonkeyPatch
):
    # given
    secret_name = "MY_SECRET"
    expected_value = "my_secret_value"
    monkeypatch.setenv("USE_KEY_VAULT", "true")
    secret_client.return_value.get_secret.return_value.value = expected_value
    secret_helper = SecretHelper()

    # when
    actual_value = secret_helper.get_secret(secret_name)

    # then
    assert actual_value == expected_value


def test_get_secret_returns_empty_string_when_secret_name_is_empty():
    # given
    secret_name = ""
    expected_value = ""
    secret_helper = SecretHelper()

    # when
    actual_value = secret_helper.get_secret(secret_name)

    # then
    assert actual_value == expected_value
