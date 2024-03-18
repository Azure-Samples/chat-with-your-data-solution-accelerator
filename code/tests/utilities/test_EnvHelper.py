from pytest import MonkeyPatch
from backend.batch.utilities.helpers.EnvHelper import EnvHelper


def test_openai_base_url_generates_url_based_on_resource_name_if_not_set(
    monkeypatch: MonkeyPatch,
):
    # given
    openai_resource_name = "some-openai-resource"
    monkeypatch.delenv("OPENAI_API_BASE")
    monkeypatch.setenv("AZURE_OPENAI_RESOURCE", openai_resource_name)

    # when
    actual_open_api_base = EnvHelper().OPENAI_API_BASE

    # then
    assert actual_open_api_base == f"https://{openai_resource_name}.openai.azure.com/"


def test_openai_base_url_uses_env_var_if_set(monkeypatch: MonkeyPatch):
    # given
    expected_openai_api_base = "some-openai-resource-base"
    monkeypatch.setenv("OPENAI_API_BASE", expected_openai_api_base)

    # when
    actual_open_api_base = EnvHelper().OPENAI_API_BASE

    # then
    assert actual_open_api_base == expected_openai_api_base
