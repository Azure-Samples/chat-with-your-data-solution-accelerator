from .orchestration_strategy import OrchestrationStrategy
from .open_ai_functions import OpenAIFunctionsOrchestrator
from .lang_chain_agent import LangChainAgent
from .semantic_kernel import SemanticKernelOrchestrator
from .prompt_flow import PromptFlowOrchestrator


def get_orchestrator(orchestration_strategy: str):
    if orchestration_strategy == OrchestrationStrategy.OPENAI_FUNCTION.value:
        return OpenAIFunctionsOrchestrator()
    elif orchestration_strategy == OrchestrationStrategy.LANGCHAIN.value:
        return LangChainAgent()
    elif orchestration_strategy == OrchestrationStrategy.SEMANTIC_KERNEL.value:
        return SemanticKernelOrchestrator()
    elif orchestration_strategy == OrchestrationStrategy.PROMPT_FLOW.value:
        return PromptFlowOrchestrator()
    else:
        raise Exception(f"Unknown orchestration strategy: {orchestration_strategy}")
