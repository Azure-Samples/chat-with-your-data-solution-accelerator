import logging
import os
import azure.functions as func
from add_url_embeddings import bp_add_url_embeddings
from batch_push_results import bp_batch_push_results
from batch_start_processing import bp_batch_start_processing
from get_conversation_response import bp_get_conversation_response
from combine_pages_chunknos import bp_combine_pages_and_chunknos
from azure.monitor.opentelemetry import configure_azure_monitor

logging.captureWarnings(True)

# Logging configuration from environment variables
AZURE_BASIC_LOGGING_LEVEL = os.environ.get("LOGLEVEL", "INFO")
PACKAGE_LOGGING_LEVEL = os.environ.get("PACKAGE_LOGGING_LEVEL", "WARNING")
AZURE_LOGGING_PACKAGES = os.environ.get("AZURE_LOGGING_PACKAGES", "")
AZURE_LOGGING_PACKAGES = [pkg.strip() for pkg in AZURE_LOGGING_PACKAGES if pkg.strip()]

# Configure logging levels from environment variables
logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL.upper(), logging.INFO)
)

# Configure Azure package logging levels
azure_package_log_level = getattr(
    logging, PACKAGE_LOGGING_LEVEL.upper(), logging.WARNING
)
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(azure_package_log_level)

if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)  # change to ANONYMOUS for local debugging
app.register_functions(bp_add_url_embeddings)
app.register_functions(bp_batch_push_results)
app.register_functions(bp_batch_start_processing)
app.register_functions(bp_get_conversation_response)
app.register_functions(bp_combine_pages_and_chunknos)
