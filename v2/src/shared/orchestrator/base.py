"""Base class for orchestration strategies.

Provides the handle_message() pipeline:
  content_safety_input → orchestrate() → content_safety_output → log_tokens → conversation_logger
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import uuid4

from shared.config.config_helper import ConfigHelper
from shared.llm.llm_helper import LLMHelper
from shared.parsers.output_parser import OutputParser
from shared.tools.content_safety import ContentSafetyChecker

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)


class OrchestratorBase(ABC):
    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings
        self.config = ConfigHelper.get_active_config_or_default()
        self.llm_helper = LLMHelper(settings)
        self.content_safety = ContentSafetyChecker(settings)
        self.message_id = str(uuid4())
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}

    def log_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Accumulate token counts across multi-step tool calls."""
        self.tokens["prompt"] += prompt_tokens or 0
        self.tokens["completion"] += completion_tokens or 0
        self.tokens["total"] += (prompt_tokens or 0) + (completion_tokens or 0)

    def call_content_safety_input(self, user_message: str) -> list[dict] | None:
        """Pre-filter: return formatted message if harmful, else None."""
        filtered = self.content_safety.validate_input(user_message)
        if user_message != filtered:
            return OutputParser.parse(question=user_message, answer=filtered)
        return None

    def call_content_safety_output(
        self, user_message: str, answer: str
    ) -> list[dict] | None:
        """Post-filter: return formatted message if harmful, else None."""
        filtered = self.content_safety.validate_output(answer)
        if answer != filtered:
            return OutputParser.parse(question=user_message, answer=filtered)
        return None

    async def handle_message(
        self,
        user_message: str,
        chat_history: list[dict],
        conversation_id: str | None = None,
        **kwargs,
    ) -> list[dict]:
        """Main pipeline: safety → orchestrate → safety → log → return messages."""

        # Dispatch to strategy-specific orchestration
        result = await self.orchestrate(user_message, chat_history, **kwargs)

        # Token logging via Azure Monitor custom dimensions (respects config flag)
        if self.config.logging.log_tokens and self.tokens["total"] > 0:
            custom_dimensions = {
                "conversation_id": conversation_id or "",
                "message_id": self.message_id,
                "prompt_tokens": self.tokens["prompt"],
                "completion_tokens": self.tokens["completion"],
                "total_tokens": self.tokens["total"],
            }
            logger.info("Token Consumption", extra={"custom_dimensions": custom_dimensions})

        # Conversation logging (if enabled)
        if self.config.logging.log_user_interactions:
            # TODO: integrate ConversationLogger when chat history DB is implemented
            logger.debug(
                "Would log user interaction for conversation_id=%s",
                conversation_id,
            )

        return result

    @abstractmethod
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> list[dict]:
        """Strategy-specific orchestration. Returns [tool_msg, assistant_msg] pair."""
        ...
