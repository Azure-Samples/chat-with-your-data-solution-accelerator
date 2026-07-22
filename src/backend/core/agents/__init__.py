"""Built-in agent definitions for CWYD v2 (package marker only).

The `agents` package owns *what an agent is* -- a Pydantic-frozen
declaration of name, instructions, deployment, and tools. It does not
own *how an agent is created* -- that belongs to the registry-backed
agents provider in ``backend/core/providers/agents/`` (see ADR 0008,
lazy-foundry-agent-bootstrap). Definitions are declarative product
policy; providers are the runtime adapter.

Hard Rule #13: this file is a package marker only. The actual
``AgentDefinition`` class plus the ``CWYD_AGENT``, ``RAI_AGENT``, and
``BUILTIN_AGENTS`` instances live in the sibling
``definitions`` module. Callers import them explicitly::

    from backend.core.agents.definitions import CWYD_AGENT, RAI_AGENT

No re-export shim and no ``__all__`` -- Hard Rule #13 forbids both.
"""
