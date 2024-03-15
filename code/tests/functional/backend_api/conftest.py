from multiprocessing import Process
import socket
import time
import pytest
import requests
from app import app
from tests.functional.backend_api.app_config import AppConfig


@pytest.fixture(scope="module")
def app_port() -> int:
    print("Getting free port")
    return get_free_port()


@pytest.fixture(scope="module")
def app_url(app_port: int) -> int:
    return f"http://localhost:{app_port}"


@pytest.fixture(scope="module")
def app_config() -> AppConfig:
    return AppConfig()


@pytest.fixture(scope="module", autouse=True)
def manage_app(app_port: int, app_config: AppConfig):
    app_config.apply_to_environment()
    app_process = start_app(app_port)
    yield
    stop_app(app_process)
    app_config.remove_from_environment()


def start_app(port: int) -> Process:
    print(f"Starting application on port {port}")
    proc = Process(target=app.run, kwargs={"port": port, "debug": True})
    proc.start()
    wait_for_app(port)
    print("Application started")
    return proc


def stop_app(proc: Process):
    print("Shutting down application")
    proc.terminate()
    proc.join()  # Wait until the process is fully shut down
    print("Application shut down")


def wait_for_app(port: int):
    attempts = 0

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
