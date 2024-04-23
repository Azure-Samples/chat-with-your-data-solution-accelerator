import json
import pytest
from unittest.mock import patch, MagicMock
from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper, Config


@pytest.fixture
def config_dict():
    return {
        "prompts": {
            "condense_question_prompt": "mock_condense_question_prompt",
            "answering_system_prompt": "mock_answering_system_prompt",
            "answering_user_prompt": "mock_answering_user_prompt",
            "answering_prompt": "mock_answering_prompt",
            "use_on_your_data_format": True,
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


@pytest.fixture
def old_config_dict():
    return {
        "prompts": {
            "condense_question_prompt": "mock_condense_question_prompt",
            "answering_prompt": "mock_answering_prompt",
            "post_answering_prompt": "mock_post_answering_prompt",
            "enable_post_answering_prompt": False,
            "enable_content_safety": True,
        },
        "messages": {
            "post_answering_filter": "mock_post_answering_filter",
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


@pytest.fixture()
def config_mock(config_dict: dict):
    return Config(config_dict)


@pytest.fixture(autouse=True)
def AzureBlobStorageClientMock():
    with patch(
        "backend.batch.utilities.helpers.ConfigHelper.AzureBlobStorageClient"
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def blob_client_mock(config_dict: dict, AzureBlobStorageClientMock: MagicMock):
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


@pytest.fixture(autouse=True)
def reset_default_config():
    ConfigHelper._default_config = None
    yield
    ConfigHelper._default_config = None


def test_default_config(env_helper_mock: MagicMock):
    # when
    env_helper_mock.ORCHESTRATION_STRATEGY = "mock-strategy"
    default_config = ConfigHelper.get_default_config()

    # then
    assert default_config["orchestrator"]["strategy"] == "mock-strategy"


def test_default_config_is_cached():
    # when
    default_config_one = ConfigHelper.get_default_config()
    default_config_two = ConfigHelper.get_default_config()

    # then
    assert default_config_one is default_config_two


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
    get_default_config_mock: MagicMock,
    config_dict: MagicMock,
    blob_client_mock: MagicMock,
):
    # given
    blob_client_mock.file_exists.return_value = False
    config_dict["prompts"][
        "answering_system_prompt"
    ] = "mock_default_answering_system_prompt"
    get_default_config_mock.return_value = config_dict

    # when
    config = ConfigHelper.get_active_config_or_default()

    # then
    assert isinstance(config, Config)
    assert (
        config.prompts.answering_system_prompt == "mock_default_answering_system_prompt"
    )


def test_save_config_as_active(
    AzureBlobStorageClientMock: MagicMock,
    blob_client_mock: MagicMock,
    config_dict: dict,
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


def test_delete_config(AzureBlobStorageClientMock: MagicMock):
    # when
    ConfigHelper.delete_config()

    # then
    AzureBlobStorageClientMock.assert_called_once_with(container_name="config")
    AzureBlobStorageClientMock.return_value.delete_file.assert_called_once_with(
        "active.json"
    )


def test_get_available_document_types(config_mock: Config):
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


def test_get_available_chunking_strategies(config_mock: Config):
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


def test_get_available_loading_strategies(config_mock: Config):
    # when
    loading_strategies = config_mock.get_available_loading_strategies()

    # then
    assert sorted(loading_strategies) == sorted(["layout", "read", "web", "docx"])


def test_get_available_orchestration_strategies(config_mock: Config):
    # when
    orchestration_strategies = config_mock.get_available_orchestration_strategies()

    # then
    assert sorted(orchestration_strategies) == sorted(["openai_function", "langchain"])


@patch("backend.batch.utilities.helpers.ConfigHelper.ConfigHelper.get_default_config")
def test_loading_old_config(
    get_default_config_mock: MagicMock,
    config_dict: dict,
    old_config_dict: dict,
    blob_client_mock: MagicMock,
):
    # given
    get_default_config_mock.return_value = config_dict
    blob_client_mock.download_file.return_value = json.dumps(old_config_dict)

    # when
    config = ConfigHelper.get_active_config_or_default()

    # then
    assert config.prompts.answering_system_prompt == "mock_answering_system_prompt"
    assert config.prompts.answering_user_prompt == "mock_answering_user_prompt"
    assert config.prompts.use_on_your_data_format is True
    assert config.example.documents == "mock_documents"
    assert config.example.user_question == "mock_user_question"
    assert config.example.answer == "mock_answer"


@patch("backend.batch.utilities.helpers.ConfigHelper.ConfigHelper.get_default_config")
def test_loading_old_config_with_modified_prompt(
    get_default_config_mock: MagicMock,
    config_dict: dict,
    old_config_dict: dict,
    blob_client_mock: MagicMock,
):
    # given
    old_config_dict["prompts"]["answering_prompt"] = "new_mock_answering_prompt"
    get_default_config_mock.return_value = config_dict
    blob_client_mock.download_file.return_value = json.dumps(old_config_dict)

    # when
    config = ConfigHelper.get_active_config_or_default()

    # then
    assert config.prompts.answering_system_prompt == "mock_answering_system_prompt"
    assert config.prompts.answering_user_prompt == "new_mock_answering_prompt"
    assert config.prompts.use_on_your_data_format is False
    assert config.example.documents == "mock_documents"
    assert config.example.user_question == "mock_user_question"
    assert config.example.answer == "mock_answer"
