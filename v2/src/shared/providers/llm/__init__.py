"""LLM provider domain (registry-keyed).

Pillar: Stable Core
Phase: 2

Foundry IQ is the production default. Additional providers (e.g.
on-prem vLLM, Ollama for dev) plug in by registering against the same
ABC -- callers always go through `llm.create(...)`, never new a
provider class directly.

Recipe (per ยง3.5 of v2/docs/development_plan.md):

    llm_provider = llm.create("foundry_iq", settings=settings, credential=cred)
    reply = await llm_provider.chat(messages, deployment="gpt-4o")
"""
from __future__ import annotations

from shared.registry import Registry

from .base import BaseLLMProvider

registry: Registry[type[BaseLLMProvider]] = Registry("llm")

# Side-effect import: triggers @registry.register("foundry_iq").
from . import foundry_iq  # noqa: E402, F401


def create(key: str, **kwargs: object) -> BaseLLMProvider:
    """Instantiate the LLM provider registered under `key`."""
    return registry.get(key)(**kwargs)


__all__ = ["BaseLLMProvider", "create", "registry"]
