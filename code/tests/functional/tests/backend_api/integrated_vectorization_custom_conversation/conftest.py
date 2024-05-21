import logging
import pytest
from pytest_httpserver import HTTPServer
from tests.functional.app_config import AppConfig
from tests.functional.tests.backend_api.common import get_free_port, start_app
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
                "AZURE_STORAGE_ACCOUNT_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "LOAD_CONFIG_FROM_BLOB_STORAGE": "False",
                "AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION": "True",
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


@pytest.fixture(scope="function", autouse=True)
def prime_search_to_trigger_creation_of_index(
    httpserver: HTTPServer, app_config: AppConfig
):
    httpserver.expect_request(
        "/indexes",
        method="GET",
    ).respond_with_json({"value": [{"name": app_config.get("AZURE_SEARCH_INDEX")}]})

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_INDEX')}')/docs/search.post.search",
        method="POST",
    ).respond_with_json(
        {
            "value": [
                {
                    "@search.score": 0.8008686,
                    "id": "aHR0cHM6Ly9zdHJ2bzRoNWZheWthd3NnLmJsb2IuY29yZS53aW5kb3dzLm5ldC9kb2N1bWVudHMvQmVuZWZpdF9PcHRpb25zLnBkZg2",
                    "content": "content",
                    "content_vector": [
                        -0.012909674,
                        0.00838491,
                    ],
                    "metadata": None,
                    "title": "doc.pdf",
                    "source": "https://source",
                    "chunk": None,
                    "offset": None,
                    "chunk_id": "31e6a74d1340_aHR0cHM6Ly9zdHJ2bzRoNWZheWthd3NnLmJsb2IuY29yZS53aW5kb3dzLm5ldC9kb2N1bWVudHMvQmVuZWZpdF9PcHRpb25zLnBkZg2_pages_6",
                }
            ]
        }
    )
