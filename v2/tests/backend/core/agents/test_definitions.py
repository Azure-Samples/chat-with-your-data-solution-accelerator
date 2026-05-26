"""Tests for shared.agents.definitions (CU-010a).

Pillar: Stable Core
Phase: Cleanup audit batch 2

Validates:

* `AgentDefinition` is frozen and rejects unknown fields.
* `CWYD_AGENT` and `RAI_AGENT` declare the required scenario data.
* `RAI_AGENT.instructions` follows the MACAE TRUE/FALSE classifier
  shape (the resolver in CU-011a parses single-token responses).
* `BUILTIN_AGENTS` is keyed by `definition.name` (the lazy resolver
  in CU-010c looks up by name).
* `deployment_attr` always names a real `OpenAISettings` field
  (catches typos like "gpt_deplyment" at definition-load time, not
  at first-request time).
"""

import pytest
from pydantic import ValidationError

from backend.core.agents.definitions import (
    BUILTIN_AGENTS,
    CWYD_AGENT,
    RAI_AGENT,
    AgentDefinition,
)
from backend.core.settings import OpenAISettings


# ---------------------------------------------------------------------------
# AgentDefinition shape
# ---------------------------------------------------------------------------


def test_agent_definition_is_frozen() -> None:
    """Built-in instances are singletons; mutation must raise so a
    consumer cannot accidentally rewrite CWYD_AGENT.instructions at
    runtime.
    """
    with pytest.raises(ValidationError):
        CWYD_AGENT.instructions = "rewritten"  # type: ignore[misc]


def test_agent_definition_rejects_extra_fields() -> None:
    """Forbidding `extra` catches drift between v2 and Foundry SDK
    field names early -- e.g. accidentally adding `system_prompt=`
    instead of `instructions=` would fail loudly here, not in
    production.
    """
    with pytest.raises(ValidationError):
        AgentDefinition(
            name="x",
            description="y",
            instructions="z",
            system_prompt="oops",  # type: ignore[call-arg]
        )


def test_agent_definition_requires_non_empty_strings() -> None:
    """An empty `name`, `description`, or `instructions` is misconfig
    that would surface as a confusing 400 from the Foundry SDK.
    Reject it at construction.
    """
    for kwargs in (
        {"name": "", "description": "ok", "instructions": "ok"},
        {"name": "ok", "description": "", "instructions": "ok"},
        {"name": "ok", "description": "ok", "instructions": ""},
    ):
        with pytest.raises(ValidationError):
            AgentDefinition(**kwargs)  # type: ignore[arg-type]


def test_agent_definition_rejects_unknown_deployment_attr() -> None:
    """`deployment_attr` is a Literal -- typos must fail at construction,
    not at first request when `getattr(settings.openai, attr)` returns
    `None` and the SDK call collapses with an opaque message.
    """
    with pytest.raises(ValidationError):
        AgentDefinition(
            name="x",
            description="y",
            instructions="z",
            deployment_attr="gpt_deplyment",  # type: ignore[arg-type]
        )


def test_agent_definition_tools_is_tuple_for_immutability() -> None:
    """Frozen models with `list` fields are still mutable through the
    list reference (`agent.tools.append(...)`). `tuple` is the
    immutable variant.
    """
    assert isinstance(CWYD_AGENT.tools, tuple)
    assert isinstance(RAI_AGENT.tools, tuple)


# ---------------------------------------------------------------------------
# Built-in instances
# ---------------------------------------------------------------------------


def test_cwyd_agent_declares_search_tool() -> None:
    """CWYD is a RAG agent -- the search tool is the whole point. If
    this regresses, the orchestrator silently falls back to ungrounded
    LLM output.
    """
    assert CWYD_AGENT.name == "cwyd"
    assert "search" in CWYD_AGENT.tools


def test_rai_agent_uses_macae_classifier_pattern() -> None:
    """The MACAE-style RAI classifier returns exactly one token
    (`TRUE` or `FALSE`). The instructions must mention both tokens
    and instruct the model to emit one of them, otherwise the parser
    in CU-011a will mis-classify ambiguous outputs.
    """
    instr = RAI_AGENT.instructions
    assert "TRUE" in instr
    assert "FALSE" in instr
    # RAI agent has no tools -- it is a pure classifier.
    assert RAI_AGENT.tools == ()


def test_builtin_agents_keyed_by_definition_name() -> None:
    """The lazy resolver (CU-010c) looks up by `definition.name`. If
    the dict key drifts from `.name`, agents would be created in
    Foundry under a key the resolver can never re-find.
    """
    for key, definition in BUILTIN_AGENTS.items():
        assert key == definition.name
    assert set(BUILTIN_AGENTS) == {"cwyd", "rai"}


def test_builtin_deployment_attrs_are_real_openai_settings_fields() -> None:
    """`deployment_attr` must name an actual `OpenAISettings` field.
    Catches typos at module-import time rather than at first request
    when `getattr(settings.openai, "gpt_deplyment")` raises.
    """
    openai_fields = set(OpenAISettings.model_fields)
    for definition in BUILTIN_AGENTS.values():
        assert definition.deployment_attr in openai_fields, (
            f"{definition.name}.deployment_attr={definition.deployment_attr!r} "
            f"is not a field on OpenAISettings ({sorted(openai_fields)})."
        )
