from azure.monitor.opentelemetry import configure_azure_monitor
from create_app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
    configure_azure_monitor()
