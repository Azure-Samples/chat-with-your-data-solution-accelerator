from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

configure_azure_monitor()
HTTPXClientInstrumentor().instrument()  # httpx is used by openai

from create_app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run()
