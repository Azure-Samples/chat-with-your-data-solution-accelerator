"""
Utility for tracking custom events to Application Insights.
"""

import os
import logging

logger = logging.getLogger(__name__)


def track_event_if_configured(event_name: str, event_data: dict):
    """Track custom event to Application Insights if configured.

    Args:
        event_name: Name of the event to track
        event_data: Dictionary of event properties
    """
    if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
        try:
            from azure.monitor.events.extension import track_event

            track_event(event_name, event_data)
        except ImportError:
            logger.warning(
                "azure-monitor-events-extension not installed. Skipping track_event for %s",
                event_name,
            )
    else:
        logger.debug(
            "Skipping track_event for %s: Application Insights is not enabled",
            event_name,
        )
