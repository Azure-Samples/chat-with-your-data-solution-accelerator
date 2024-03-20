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
