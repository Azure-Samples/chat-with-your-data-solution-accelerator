import logging
import pytest
from unittest.mock import MagicMock, patch
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


@pytest.fixture(scope="function")
def mock_postgres_connection():
    """Mock PostgreSQL connection for functional tests only (not autouse to avoid interfering with unit tests)"""
    with patch('psycopg2.connect') as mock_connect, \
         patch('backend.batch.utilities.helpers.azure_postgres_helper.get_azure_credential'):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        mock_conn.closed = 0  # Simulate open connection

        # Mock query results for vector search
        mock_cursor.fetchall.return_value = [
            {
                "id": "doc1",
                "title": "test.pdf",
                "chunk": "42 is the meaning of life",
                "offset": 0,
                "page_number": 1,
                "content": "42 is the meaning of life",
                "source": "test.pdf",
            }
        ]

        yield mock_conn


@pytest.fixture(scope="package")
def app_config(make_httpserver, ca):
    logger.info("Creating APP CONFIG for PostgreSQL")
    with ca.cert_pem.tempfile() as ca_temp_path:
        app_config = AppConfig(
            {
                # Azure OpenAI configuration (still needed for embeddings/LLM)
                "AZURE_OPENAI_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_CONTENT_SAFETY_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SPEECH_REGION_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_STORAGE_ACCOUNT_ENDPOINT": f"https://localhost:{make_httpserver.port}/",

                # PostgreSQL configuration
                "DATABASE_TYPE": "PostgreSQL",
                "POSTGRESQL_USER": "test_user",
                "POSTGRESQL_HOST": "localhost",
                "POSTGRESQL_DATABASE": "test_db",

                # Disable Azure Search
                "AZURE_SEARCH_SERVICE": None,
                "AZURE_SEARCH_INDEX": None,
                "AZURE_SEARCH_KEY": None,
                "AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION": "False",

                "LOAD_CONFIG_FROM_BLOB_STORAGE": "False",
                "ORCHESTRATION_STRATEGY": "semantic_kernel",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
            }
        )
        logger.info(f"Created PostgreSQL app config: {app_config.get_all()}")
        yield app_config


@pytest.fixture(scope="module", autouse=True)
def manage_app(app_port: int, app_config: AppConfig):
    """Manage app startup/teardown for functional tests."""
    app_config.apply_to_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
    start_app(app_port)
    yield
    app_config.remove_from_environment()
    EnvHelper.clear_instance()
    ConfigHelper.clear_config()
