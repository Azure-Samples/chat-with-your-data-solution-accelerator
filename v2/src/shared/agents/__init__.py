"""Built-in agent definitions for CWYD v2.

Pillar: Stable Core (AgentDefinition abstraction) + Scenario Pack (CWYD + RAI instances)
Phase: Cleanup audit batch 2 (CU-010a)

The `agents` package owns *what an agent is* -- a Pydantic-frozen
declaration of name, instructions, deployment, and tools. It does not
own *how an agent is created* -- that belongs to the registry-backed
agents provider in `shared/providers/agents/` (CU-010c will add
`get_or_create_agent(definition, ...)` there). Definitions are
declarative product policy; providers are the runtime adapter.

Per ADR 0008 (lazy-foundry-agent-bootstrap), agent identity is not
operator-supplied -- the runtime resolves each definition lazily on
first request and persists the resulting Foundry agent id in the
chat-history database. This module's job is to give that resolver a
stable, frozen description of *which* agents exist.
"""

from shared.agents.definitions import (
    BUILTIN_AGENTS,
    CWYD_AGENT,
    RAI_AGENT,
    AgentDefinition,
)

__all__ = [
    "AgentDefinition",
    "BUILTIN_AGENTS",
    "CWYD_AGENT",
    "RAI_AGENT",
]
