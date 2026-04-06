"""Content safety middleware for LangGraph."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ContentSafetyMiddleware:
    """Wraps Azure AI Content Safety as LangGraph middleware."""

    # TODO: Phase 2.5 — wrap langchain_azure_ai.agents.middleware.content_safety
    pass
