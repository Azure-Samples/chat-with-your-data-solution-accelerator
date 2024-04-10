import json
import pytest
from unittest.mock import patch, MagicMock
from azure.core.exceptions import ResourceNotFoundError
from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper, Config


config_dict = {
    "prompts": {
        "condense_question_prompt": "mock_condense_question_prompt",
        "answering_prompt": "mock_answering_prompt",
        "answering_system_prompt": "mock_answering_system_prompt",
        "answering_user_prompt": "mock_answering_user_prompt",
        "post_answering_prompt": "mock_post_answering_prompt",
        "enable_post_answering_prompt": False,
        "enable_content_safety": True,
    },
    "messages": {
        "post_answering_filter": "mock_post_answering_filter",
    },
    "example": {
        "documents": "mock_documents",
        "user_question": "mock_user_question",
        "answer": "mock_answer",
    },
    "document_processors": [
        {
            "document_type": "jpg",
            "chunking": {
                "strategy": "layout",
                "size": 500,
                "overlap": 100,
            },
            "loading": {
                "strategy": "web",
            },
        },
    ],
    "logging": {
        "log_user_interactions": True,
        "log_tokens": True,
    },
    "orchestrator": {
        "strategy": "langchain",
    },
}
config_mock = Config(config_dict)


@pytest.fixture(autouse=True)
def AzureBlobStorageClientMock():
    with patch(
        "backend.batch.utilities.helpers.ConfigHelper.AzureBlobStorageClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def blob_client_mock(AzureBlobStorageClientMock: MagicMock):
    mock = AzureBlobStorageClientMock.return_value
    mock.download_file.return_value = json.dumps(config_dict)

    return mock


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.helpers.ConfigHelper.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.ORCHESTRATION_STRATEGY = "openai_function"
        env_helper.LOAD_CONFIG_FROM_BLOB_STORAGE = True

        yield env_helper


def test_get_config_from_azure(
    AzureBlobStorageClientMock: MagicMock,
    blob_client_mock: MagicMock,
):
    # when
    config = ConfigHelper.get_active_config_or_default()

    # then
    AzureBlobStorageClientMock.assert_called_once_with(container_name="config")
    blob_client_mock.download_file.assert_called_once_with("active.json")

    assert config.prompts.condense_question_prompt == "mock_condense_question_prompt"


@patch("backend.batch.utilities.helpers.ConfigHelper.ConfigHelper.get_default_config")
def test_get_default_config_when_not_in_azure(
    get_default_config_mock: MagicMock, blob_client_mock: MagicMock
):
    # given
    get_default_config_mock.return_value = Config(config_dict)
    blob_client_mock.download_file.side_effect = ResourceNotFoundError()

    # when
    default_config = ConfigHelper.get_default_config()
    config = ConfigHelper.get_active_config_or_default()

    # then
    assert config is default_config


def test_save_config_as_active(
    AzureBlobStorageClientMock: MagicMock,
    blob_client_mock: MagicMock,
):
    # when
    ConfigHelper.save_config_as_active(config_dict)

    # then
    AzureBlobStorageClientMock.assert_called_once_with(container_name="config")
    blob_client_mock.upload_file.assert_called_once_with(
        json.dumps(config_dict, indent=2),
        "active.json",
        content_type="application/json",
    )


def test_get_available_document_types():
    # when
    document_types = config_mock.get_available_document_types()

    # then
    assert sorted(document_types) == sorted(
        [
            "txt",
            "pdf",
            "url",
            "html",
            "md",
            "jpeg",
            "jpg",
            "png",
            "docx",
        ]
    )


def test_get_available_chunking_strategies():
    # when
    chunking_strategies = config_mock.get_available_chunking_strategies()

    # then
    assert sorted(chunking_strategies) == sorted(
        [
            "layout",
            "page",
            "fixed_size_overlap",
            "paragraph",
        ]
    )


def test_get_available_loading_strategies():
    # when
    loading_strategies = config_mock.get_available_loading_strategies()

    # then
    assert sorted(loading_strategies) == sorted(["layout", "read", "web", "docx"])


def test_get_available_orchestration_strategies():
    # when
    orchestration_strategies = config_mock.get_available_orchestration_strategies()

    # then
    assert sorted(orchestration_strategies) == sorted(["openai_function", "langchain"])
