import logging
import os
import azure.functions as func
from add_url_embeddings import bp_add_url_embeddings
from batch_push_results import bp_batch_push_results
from batch_start_processing import bp_batch_start_processing
from get_conversation_response import bp_get_conversation_response
from azure.monitor.opentelemetry import configure_azure_monitor

logging.captureWarnings(True)
# Raising the azure log level to WARN as it is too verbose - https://github.com/Azure/azure-sdk-for-python/issues/9422
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())
if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)  # change to ANONYMOUS for local debugging
app.register_functions(bp_add_url_embeddings)
app.register_functions(bp_batch_push_results)
app.register_functions(bp_batch_start_processing)
app.register_functions(bp_get_conversation_response)
