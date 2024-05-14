from typing import List

from ..orchestrator.orchestration_strategy import OrchestrationStrategy
from ..orchestrator import OrchestrationSettings
from ..orchestrator.strategies import get_orchestrator

__all__ = ["OrchestrationStrategy"]


class Orchestrator:
    def __init__(self) -> None:
        pass

    async def handle_message(
        self,
        user_message: str,
        chat_history: List[dict],
        conversation_id: str,
        orchestrator: OrchestrationSettings,
        **kwargs: dict,
    ) -> dict:
        orchestrator = get_orchestrator(orchestrator.strategy.value)
        if orchestrator is None:
            raise Exception(
                f"Unknown orchestration strategy: {orchestrator.strategy.value}"
            )
        return await orchestrator.handle_message(
            user_message, chat_history, conversation_id
        )
