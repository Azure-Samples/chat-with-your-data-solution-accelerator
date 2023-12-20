from enum import Enum


class OrchestrationStrategy(Enum):
    """
    Enumeration representing different orchestration strategies.
    """

    OPENAI_FUNCTION = 'openai_function'
    LANGCHAIN = 'langchain'


def get_orchestrator(orchestration_strategy: str):
    """
    Returns an instance of the orchestrator based on the specified orchestration strategy.

    Args:
        orchestration_strategy (str): The orchestration strategy to use.

    Returns:
        Orchestrator: An instance of the orchestrator.

    Raises:
        Exception: If the specified orchestration strategy is unknown.
    """
    if orchestration_strategy == OrchestrationStrategy.OPENAI_FUNCTION.value:
        from .OpenAIFunctions import OpenAIFunctionsOrchestrator
        return OpenAIFunctionsOrchestrator()
    elif orchestration_strategy == OrchestrationStrategy.LANGCHAIN.value:
        from .LangChainAgent import LangChainAgent
        return LangChainAgent()
    else:
        raise Exception(
            f"Unknown orchestration strategy: {orchestration_strategy}")
