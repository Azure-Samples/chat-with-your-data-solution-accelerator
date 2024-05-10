import logging
import pytest
from tests.functional.backend_api.app_config import AppConfig
from tests.functional.backend_api.common import get_free_port, start_app
from backend.batch.utilities.helpers.config.config_helper import ConfigHelper
from backend.batch.utilities.helpers.env_helper import EnvHelper

logger = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def app_port() -> int:
    logger.info("Getting free port")
    return get_free_port()


@pytest.fixture(scope="package")
def app_url(app_port: int) -> str:
    return f"http://localhost:{app_port}"


@pytest.fixture(scope="package")
def app_config(make_httpserver, ca):
    logger.info("Creating APP CONFIG")
    with ca.cert_pem.tempfile() as ca_temp_path:
        app_config = AppConfig(
            {
                "AZURE_OPENAI_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SEARCH_SERVICE": f"https://localhost:{make_httpserver.port}/",
                "AZURE_CONTENT_SAFETY_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SPEECH_REGION_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
            }
        )
        logger.info(f"Created app config: {app_config.get_all()}")
        yield app_config


@pytest.fixture(scope="package", autouse=True)
def manage_app(app_port: int, app_config: AppConfig):
    app_config.apply_to_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
    start_app(app_port)
    yield
    app_config.remove_from_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
