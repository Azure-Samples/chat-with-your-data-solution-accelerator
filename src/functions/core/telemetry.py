"""Azure Monitor / OpenTelemetry export for the Functions worker.

The Functions host provides the App Insights connection string under the
standard env var name ``APPLICATIONINSIGHTS_CONNECTION_STRING`` (the
backend container uses the ``AZURE_``-prefixed typed name instead -- see
ADR 0018). When set, :func:`configure_telemetry` configures the Azure
Monitor exporter so the worker's application telemetry (logs / traces /
dependencies) reaches Application Insights; absent (local dev /
monitoring disabled) it is a no-op.

This lives in ``functions.core`` -- not ``function_app.py`` -- so the host
entry module stays a thin blueprint-registration surface with no logic.
"""

import logging
import os

from azure.monitor.opentelemetry import (
    configure_azure_monitor,
)  # pyright: ignore[reportUnknownVariableType]

logger = logging.getLogger(__name__)

_APPLICATIONINSIGHTS_CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"


def configure_telemetry() -> bool:
    """Wire Azure Monitor OpenTelemetry export for the Functions worker.

    Reads the host-provided ``APPLICATIONINSIGHTS_CONNECTION_STRING`` and,
    when set, configures the Azure Monitor exporter so the worker's
    application telemetry reaches Application Insights. Absent (local dev
    / monitoring disabled) it is a no-op. Returns ``True`` when telemetry
    was configured, ``False`` when skipped.
    """
    conn_str = os.environ.get(_APPLICATIONINSIGHTS_CONNECTION_STRING, "").strip()
    if not conn_str:
        logger.info(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set; "
            "function telemetry disabled."
        )
        return False
    configure_azure_monitor(connection_string=conn_str)
    logger.info("Application Insights telemetry configured for functions.")
    return True
