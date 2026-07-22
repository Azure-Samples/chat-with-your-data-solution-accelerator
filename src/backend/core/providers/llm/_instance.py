"""Registry instance for the LLM provider domain.

Holds the `Registry[type[BaseLLMProvider]]` instance in a leaf module
so `registry.py` can be top-imports-only per Hard Rule #17. The
public surface (eager concrete import of `foundry_iq`) stays in
`registry.py`.
"""

from backend.core.registry import Registry

from .base import BaseLLMProvider

registry: Registry[type[BaseLLMProvider]] = Registry("llm")
