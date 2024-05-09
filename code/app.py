import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logging.captureWarnings(True)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())
# Raising the azure log level to WARN as it is too verbose - https://github.com/Azure/azure-sdk-for-python/issues/9422
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())
# We cannot use EnvHelper here as Application Insights should be configured first
# for instrumentation to work correctly
if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()
    HTTPXClientInstrumentor().instrument()  # httpx is used by openai

from create_app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run()
