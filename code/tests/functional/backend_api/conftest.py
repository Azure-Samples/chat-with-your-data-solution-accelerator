import logging
import socket
import ssl
import threading
import time
import pytest
from pytest_httpserver import HTTPServer
import requests
from tests.functional.backend_api.app_config import AppConfig
from threading import Thread
import trustme
import importlib
from app import app as flask_app
import app


@pytest.fixture(scope="session")
def ca():
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    return trustme.CA()


@pytest.fixture(scope="session")
def httpserver_ssl_context(ca):
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    localhost_cert = ca.issue_cert("localhost")
    localhost_cert.configure_cert(context)
    return context


@pytest.fixture(scope="session")
def httpclient_ssl_context(ca):
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    with ca.cert_pem.tempfile() as ca_temp_path:
        return ssl.create_default_context(cafile=ca_temp_path)


@pytest.fixture(scope="session")
def app_port() -> int:
    logging.info("Getting free port")
    return get_free_port()


@pytest.fixture(scope="session")
def app_url(app_port: int) -> str:
    return f"http://localhost:{app_port}"


@pytest.fixture(scope="session")
def app_config(make_httpserver, ca):
    logging.info("Creating APP CONFIG")
    with ca.cert_pem.tempfile() as ca_temp_path:
        app_config = AppConfig(
            {
                "AZURE_OPENAI_ENDPOINT": f"https://localhost:{make_httpserver.port}",
                "AZURE_SEARCH_SERVICE": f"https://localhost:{make_httpserver.port}",
                "AZURE_CONTENT_SAFETY_ENDPOINT": f"https://localhost:{make_httpserver.port}",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
            }
        )
        logging.info(f"Created app config: {app_config.get_all()}")
        yield app_config


@pytest.fixture(scope="session", autouse=True)
def manage_app(app_port: int, app_config: AppConfig):
    app_config.apply_to_environment()
    start_app(app_port)
    yield
    app_config.remove_from_environment()


@pytest.fixture(scope="function", autouse=True)
def setup_default_mocking(httpserver: HTTPServer, app_config: AppConfig):
    httpserver.expect_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_EMBEDDING_MODEL')}/embeddings",
        method="POST",
    ).respond_with_json(
        {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": [0.018990106880664825, -0.0073809814639389515],
                    "index": 0,
                }
            ],
            "model": "text-embedding-ada-002",
        }
    )

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')",
        method="GET",
    ).respond_with_json({})

    httpserver.expect_request(
        "/contentsafety/text:analyze",
        method="POST",
    ).respond_with_json(
        {
            "blocklistsMatch": [],
            "categoriesAnalysis": [],
        }
    )

    httpserver.expect_request(
        f"/openai/deployments/{app_config.get('AZURE_OPENAI_MODEL')}/chat/completions",
        method="POST",
    ).respond_with_json(
        {
            "id": "chatcmpl-6v7mkQj980V1yBec6ETrKPRqFjNw9",
            "object": "chat.completion",
            "created": 1679072642,
            "model": "gpt-35-turbo",
            "usage": {
                "prompt_tokens": 58,
                "completion_tokens": 68,
                "total_tokens": 126,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "42 is the meaning of life",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
        }
    )

    httpserver.expect_request(
        f"/indexes('{app_config.get('AZURE_SEARCH_CONVERSATIONS_LOG_INDEX')}')/docs/search.index",
        method="POST",
    ).respond_with_json(
        {
            "value": [
                {"key": "1", "status": True, "errorMessage": None, "statusCode": 201}
            ]
        }
    )

    yield

    httpserver.check()


def start_app(app_port: int) -> Thread:
    logging.info(f"Starting application on port {app_port}")
    # ensure app is reloaded now that new environment variables are set
    importlib.reload(app)
    app_process = threading.Thread(target=lambda: flask_app.run(port=app_port))
    app_process.daemon = True
    app_process.start()
    wait_for_app(app_port)
    logging.info("Application started")
    return app_process


def wait_for_app(port: int, initial_check_delay: int = 10):
    attempts = 0
    time.sleep(initial_check_delay)
    while attempts < 10:
        try:
            response = requests.get(f"http://localhost:{port}/api/config")
            if response.status_code == 200:
                return
        except Exception:
            pass

        attempts += 1
        time.sleep(1)

    raise Exception("App failed to start")


def get_free_port() -> int:
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    _, port = s.getsockname()
    s.close()
    return port
