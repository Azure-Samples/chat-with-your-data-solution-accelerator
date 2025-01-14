from unittest.mock import patch
from pytest import MonkeyPatch
import pytest
from backend.batch.utilities.helpers.env_helper import EnvHelper


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
        monkeypatch.setenv("APPLICATIONINSIGHTS_ENABLED", value)

    # when
    actual_APPLICATIONINSIGHTS_enabled = EnvHelper().APPLICATIONINSIGHTS_ENABLED

    # then
    assert actual_APPLICATIONINSIGHTS_enabled == expected


def test_keys_are_unset_when_auth_type_rbac(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("AZURE_AUTH_TYPE", "rbac")

    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.AZURE_SEARCH_KEY is None
    assert env_helper.AZURE_OPENAI_API_KEY == ""
    assert env_helper.AZURE_SPEECH_KEY is None
    assert env_helper.AZURE_COMPUTER_VISION_KEY is None


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


def test_get_env_var_array(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("AZURE_SPEECH_RECOGNIZER_LANGUAGES", "en-US,es-ES")

    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.AZURE_SPEECH_RECOGNIZER_LANGUAGES == ["en-US", "es-ES"]


def test_azure_speech_recognizer_languages_default(monkeypatch: MonkeyPatch):
    # given - no env var set

    # when
    env_helper = EnvHelper()

    # then
    assert env_helper.AZURE_SPEECH_RECOGNIZER_LANGUAGES == ["en-US"]


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("false", False), ("this is the way", False), (None, False)],
)
def test_use_advanced_image_processing(monkeypatch: MonkeyPatch, value, expected):
    # given
    monkeypatch.setenv("DATABASE_TYPE", "CosmosDB")
    if value is not None:
        monkeypatch.setenv("USE_ADVANCED_IMAGE_PROCESSING", value)

    # when
    actual_use_advanced_image_processing = EnvHelper().USE_ADVANCED_IMAGE_PROCESSING

    # then
    assert actual_use_advanced_image_processing == expected


@patch(
    "backend.batch.utilities.helpers.env_helper.os.getenv",
    side_effect=Exception("Some error"),
)
def test_env_helper_not_created_if_error_occurs(_):
    # when
    with pytest.raises(Exception):
        EnvHelper()

    # then
    assert EnvHelper._instance is None


def test_database_type_if_set_as_postgresql(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("DATABASE_TYPE", "PostgreSQL")
    expected_postgres_user = "some-postgres-user"
    expected_postgres_database_name = "some-postgres-database-name"
    expected_postgres_host_name = "some-postgres-host-name"
    expected_postgres_info = '{"user":"some-postgres-user","dbname":"some-postgres-database-name","host":"some-postgres-host-name"}'
    monkeypatch.setenv("AZURE_POSTGRESQL_INFO", expected_postgres_info)

    # when
    env_helper = EnvHelper()
    azure_postgresql_info = env_helper.get_info_from_env("AZURE_POSTGRESQL_INFO", {})
    actual_postgres_user = azure_postgresql_info.get("user", "")
    actual_postgres_database_name = azure_postgresql_info.get("dbname", "")
    actual_postgres_host_name = azure_postgresql_info.get("host", "")

    # then
    assert actual_postgres_user == expected_postgres_user
    assert actual_postgres_database_name == expected_postgres_database_name
    assert actual_postgres_host_name == expected_postgres_host_name


def test_use_advanced_image_processing_postgresql(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("DATABASE_TYPE", "PostgreSQL")
    monkeypatch.setenv("USE_ADVANCED_IMAGE_PROCESSING", False)

    # when
    actual_use_advanced_image_processing = EnvHelper().USE_ADVANCED_IMAGE_PROCESSING

    # then
    assert not actual_use_advanced_image_processing


def test_use_integrated_vectorization_postgresql(monkeypatch: MonkeyPatch):
    # given
    monkeypatch.setenv("DATABASE_TYPE", "PostgreSQL")
    monkeypatch.setenv("AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION", False)

    # when
    actual_use_integrated_vectorization = (
        EnvHelper().AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION
    )

    # then
    assert not actual_use_integrated_vectorization
