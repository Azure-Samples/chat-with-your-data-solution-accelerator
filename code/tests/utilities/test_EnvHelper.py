from pytest import MonkeyPatch
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


def test_load_config_from_blob_storage_true_when_unset():
    # given
    expected_load_config_from_blob_storage = True

    # when
    actual_load_config_from_blob_storage = EnvHelper().LOAD_CONFIG_FROM_BLOB_STORAGE

    # then
    assert (
        actual_load_config_from_blob_storage == expected_load_config_from_blob_storage
    )


def test_load_config_from_blob_storage_true_when_true(monkeypatch: MonkeyPatch):
    # given
    expected_load_config_from_blob_storage = True
    monkeypatch.setenv("LOAD_CONFIG_FROM_BLOB_STORAGE", "true")

    # when
    actual_load_config_from_blob_storage = EnvHelper().LOAD_CONFIG_FROM_BLOB_STORAGE

    # then
    assert (
        actual_load_config_from_blob_storage == expected_load_config_from_blob_storage
    )


def test_load_config_from_blob_storage_false_when_false(monkeypatch: MonkeyPatch):
    # given
    expected_load_config_from_blob_storage = False
    monkeypatch.setenv("LOAD_CONFIG_FROM_BLOB_STORAGE", "false")

    # when
    actual_load_config_from_blob_storage = EnvHelper().LOAD_CONFIG_FROM_BLOB_STORAGE

    # then
    assert (
        actual_load_config_from_blob_storage == expected_load_config_from_blob_storage
    )


def test_load_config_from_blob_storage_false_when_random(monkeypatch: MonkeyPatch):
    # given
    expected_load_config_from_blob_storage = False
    monkeypatch.setenv("LOAD_CONFIG_FROM_BLOB_STORAGE", "this is the way")

    # when
    actual_load_config_from_blob_storage = EnvHelper().LOAD_CONFIG_FROM_BLOB_STORAGE

    # then
    assert (
        actual_load_config_from_blob_storage == expected_load_config_from_blob_storage
    )


def test_appinsights_enabled_true_when_unset():
    # given
    expected_appinsights_enabled = True

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected_appinsights_enabled


def test_appinsights_enabled_true_when_true(monkeypatch: MonkeyPatch):
    # given
    expected_appinsights_enabled = True
    monkeypatch.setenv("APPINSIGHTS_ENABLED", "true")

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected_appinsights_enabled


def test_appinsights_enabled_false_when_false(monkeypatch: MonkeyPatch):
    # given
    expected_appinsights_enabled = False
    monkeypatch.setenv("APPINSIGHTS_ENABLED", "false")

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected_appinsights_enabled


def test_appinsights_enabled_false_when_random(monkeypatch: MonkeyPatch):
    # given
    expected_appinsights_enabled = False
    monkeypatch.setenv("APPINSIGHTS_ENABLED", "this is the way")

    # when
    actual_appinsights_enabled = EnvHelper().APPINSIGHTS_ENABLED

    # then
    assert actual_appinsights_enabled == expected_appinsights_enabled
