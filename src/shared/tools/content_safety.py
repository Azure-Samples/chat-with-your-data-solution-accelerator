"""Content safety checker: Azure AI Content Safety pre/post filter."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions
from azure.core.credentials import AzureKeyCredential

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)

_INPUT_TEMPLATE = (
    "Unfortunately, I am not able to process your question, as I have detected "
    "sensitive content that I am not allowed to process. This might be a mistake, "
    "so please try rephrasing your question."
)
_OUTPUT_TEMPLATE = (
    "Unfortunately, I have detected sensitive content in my answer, which I am "
    "not allowed to show you. This might be a mistake, so please try again and "
    "maybe rephrase your question."
)


class ContentSafetyChecker:
    """Wraps Azure AI Content Safety for input and output filtering."""

    def __init__(self, settings: EnvSettings) -> None:
        self.enabled = bool(
            settings.enable_content_safety and settings.azure_content_safety_endpoint
        )
        if self.enabled:
            if settings.auth.azure_auth_type == "keys":
                credential = AzureKeyCredential(settings.azure_content_safety_key)
            else:
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
            self.client = ContentSafetyClient(
                endpoint=settings.azure_content_safety_endpoint,
                credential=credential,
            )

    def validate_input(self, text: str) -> str:
        """Return replacement message if harmful, otherwise return original text."""
        if not self.enabled:
            return text
        return self._filter(text, _INPUT_TEMPLATE)

    def validate_output(self, text: str) -> str:
        """Return replacement message if harmful, otherwise return original text."""
        if not self.enabled:
            return text
        return self._filter(text, _OUTPUT_TEMPLATE)

    def _filter(self, text: str, replacement: str) -> str:
        try:
            response = self.client.analyze_text(AnalyzeTextOptions(text=text))
            for result in response.categories_analysis:
                if result.severity and result.severity > 0:
                    logger.warning(
                        "Content safety triggered: category=%s severity=%s",
                        result.category,
                        result.severity,
                    )
                    return replacement
        except Exception:
            logger.exception("Content safety check failed")
        return text
