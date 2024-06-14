from enum import Enum


class OrchestrationStrategy(Enum):
    OPENAI_FUNCTION = "openai_function"
    LANGCHAIN = "langchain"
    SEMANTIC_KERNEL = "semantic_kernel"
    PROMPT_FLOW = "prompt_flow"
