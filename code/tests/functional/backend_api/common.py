import logging
import socket
import threading
import time
import requests
from threading import Thread
from create_app import create_app

logger = logging.getLogger(__name__)


def start_app(app_port: int) -> Thread:
    logger.info(f"Starting application on port {app_port}")
    app = create_app()
    app_process = threading.Thread(target=lambda: app.run(port=app_port), daemon=True)
    app_process.start()
    wait_for_app(app_port)
    logger.info("Application started")
    return app_process


def wait_for_app(port: int, initial_check_delay: int = 2):
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
