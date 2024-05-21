import logging
import os
import sys
import pytest

from tests.functional.app_config import AppConfig

sys.path.append(
    os.path.join(os.path.dirname(sys.path[0]), "..", "..", "..", "backend", "batch")
)
# The below imports are needed due to the sys.path.append above as the backend function is not aware of the folders outside of the function
from utilities.helpers.config.config_helper import ConfigHelper  # noqa: E402
from utilities.helpers.env_helper import EnvHelper  # noqa: E402

logger = logging.getLogger(__name__)


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
                "AZURE_STORAGE_ACCOUNT_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION": "True",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
            }
        )
        logger.info(f"Created app config: {app_config.get_all()}")
        yield app_config


@pytest.fixture(scope="package", autouse=True)
def manage_app(app_config: AppConfig):
    app_config.apply_to_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
    yield
    app_config.remove_from_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
