from pytest import MonkeyPatch
import pytest
from backend.batch.utilities.helpers.EnvHelper import EnvHelper


@pytest.fixture(autouse=True)
def cleanup():
    EnvHelper.clear_instance()
    yield
    EnvHelper.clear_instance()


def test_env_helper_is_singleton():
    assert EnvHelper() is EnvHelper()


def test_openai_base_url_generates_url_based_on_resource_name_if_not_set(
    monkeypatch: MonkeyPatch,
):
    # given
    openai_resource_name = "some-openai-resource"
    monkeypatch.setenv("AZURE_OPENAI_RESOURCE", openai_resource_name)

    # when
    actual_openai_endpoint = EnvHelper().AZURE_OPENAI_ENDPOINT

    # then
    assert actual_openai_endpoint == f"https://{openai_resource_name}.openai.azure.com/"


def test_openai_base_url_uses_env_var_if_set(monkeypatch: MonkeyPatch):
    # given
    expected_openai_endpoint = "some-openai-resource-base"
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", expected_openai_endpoint)

    # when
    actual_openai_endpoint = EnvHelper().AZURE_OPENAI_ENDPOINT

    # then
    assert actual_openai_endpoint == expected_openai_endpoint


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("false", False), ("this is the way", False), (None, True)],
)
def test_load_config_from_blob_storage(monkeypatch: MonkeyPatch, value, expected):
    # given
    if value is not None:
        monkeypatch.setenv("LOAD_CONFIG_FROM_BLOB_STORAGE", value)

    # when
    actual_load_config_from_blob_storage = EnvHelper().LOAD_CONFIG_FROM_BLOB_STORAGE

    # then
    assert actual_load_config_from_blob_storage == expected


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("false", False), ("this is the way", False), (None, False)],
)
def test_app_insights_enabled(monkeypatch: MonkeyPatch, value, expected):
    # given
    if value is not None:
        monkeypatch.setenv("APPINSIGHTS_ENABLED", value)

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected


def test_keys_are_unset_when_auth_type_rbac(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("AZURE_AUTH_TYPE", "rbac")

    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.AZURE_SEARCH_KEY is None
    assert env_helper.AZURE_OPENAI_API_KEY == ""
    assert env_helper.AZURE_SPEECH_KEY is None


def test_sets_default_log_level_when_unset():
    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.LOGLEVEL == "INFO"


def test_uses_and_uppercases_log_level_when_set(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("LOGLEVEL", "deBug")

    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.LOGLEVEL == "DEBUG"
