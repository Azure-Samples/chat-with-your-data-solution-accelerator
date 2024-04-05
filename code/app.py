from azure.monitor.opentelemetry import configure_azure_monitor
from create_app import create_app

configure_azure_monitor()
app = create_app()

if __name__ == "__main__":
    app.run()
