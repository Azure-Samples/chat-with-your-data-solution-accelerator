"""Base class for orchestration strategies."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from src.shared.config.env_settings import EnvSettings

logger = logging.getLogger(__name__)


class OrchestratorBase(ABC):
    def __init__(self, settings: EnvSettings) -> None:
        self.settings = settings

    @abstractmethod
    async def orchestrate(
        self,
        user_message: str,
        chat_history: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        """Process a user message and yield response chunks."""
        ...
