from .OrchestrationStrategy import OrchestrationStrategy
from .OpenAIFunctions import OpenAIFunctionsOrchestrator
from .LangChainAgent import LangChainAgent
from .SemanticKernel import SemanticKernelOrchestrator


def get_orchestrator(orchestration_strategy: str):
    if orchestration_strategy == OrchestrationStrategy.OPENAI_FUNCTION.value:
        return OpenAIFunctionsOrchestrator()
    elif orchestration_strategy == OrchestrationStrategy.LANGCHAIN.value:
        return LangChainAgent()
    elif orchestration_strategy == OrchestrationStrategy.SEMANTIC_KERNEL.value:
        return SemanticKernelOrchestrator()
    else:
        raise Exception(f"Unknown orchestration strategy: {orchestration_strategy}")
