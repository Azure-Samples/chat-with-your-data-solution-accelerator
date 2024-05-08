from enum import Enum


class OrchestrationStrategy(Enum):
    OPENAI_FUNCTION = "openai_function"
    LANGCHAIN = "langchain"
    SEMANTIC_KERNEL = "semantic_kernel"


def get_orchestrator(orchestration_strategy: str):
    if orchestration_strategy == OrchestrationStrategy.OPENAI_FUNCTION.value:
        from .OpenAIFunctions import OpenAIFunctionsOrchestrator

        return OpenAIFunctionsOrchestrator()
    elif orchestration_strategy == OrchestrationStrategy.LANGCHAIN.value:
        from .LangChainAgent import LangChainAgent

        return LangChainAgent()
    elif orchestration_strategy == OrchestrationStrategy.SEMANTIC_KERNEL.value:
        from .SemanticKernel import SemanticKernelOrchestrator

        return SemanticKernelOrchestrator()
    else:
        raise Exception(f"Unknown orchestration strategy: {orchestration_strategy}")
