from pytest import MonkeyPatch
import pytest
from backend.batch.utilities.helpers.EnvHelper import EnvHelper


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
    [("true", True), ("false", False), ("this is the way", False), (None, True)],
)
def test_app_insights_enabled(monkeypatch: MonkeyPatch, value, expected):
    # given
    if value is not None:
        monkeypatch.setenv("APPINSIGHTS_ENABLED", value)

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected
