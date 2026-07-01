"""Tests for shared.agents.definitions (CU-010a).

Pillar: Stable Core
Phase: Cleanup audit batch 2

Validates:

* `AgentDefinition` is frozen and rejects unknown fields.
* `CWYD_AGENT` and `RAI_AGENT` declare the required scenario data.
* `RAI_AGENT.instructions` follows the reference-architecture TRUE/FALSE classifier
  shape (the resolver in CU-011a parses single-token responses).
* `BUILTIN_AGENTS` is keyed by `definition.name` (the lazy resolver
  in CU-010c looks up by name).
"""

import pytest
from pydantic import ValidationError

from backend.core.agents.definitions import (
    BUILTIN_AGENTS,
    CWYD_AGENT,
    CWYD_DEFAULT_BODY,
    CWYD_GUARDRAIL,
    PROMPT_REVIEW_AGENT,
    RAI_AGENT,
    AgentDefinition,
    compose_cwyd_instructions,
    resolve_cwyd_instructions,
)


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


def test_cwyd_agent_carries_vetted_v1_default_prompt() -> None:
    """CWYD ships v1's vetted Azure-OpenAI-On-Your-Data answering
    system prompt as its default instructions. Its retrieval tool is a
    runtime MCP tool bound at `run()` time -- not a server-side tool
    baked into the agent at `create_agent` -- so `tools` stays empty (a
    stale `"search"` placeholder would be forwarded to `create_agent`
    as a bogus tool key) and the grounding intent lives in the
    instructions instead.
    """
    instr = CWYD_AGENT.instructions
    assert CWYD_AGENT.name == "cwyd"
    assert CWYD_AGENT.tools == ()
    # Grounds strictly in retrieved documents (the vetted intent).
    assert "retrieved documents" in instr.lower()
    # Carries the [doc+index] citation format the v2
    # `filter_to_referenced` citation parser depends on.
    assert "[doc+index]" in instr
    # Preserves the vetted out-of-domain refusal string.
    assert (
        "The requested information is not available in the retrieved data. "
        "Please try another query or topic."
    ) in instr
    # The stale "knowledge cutoff 2021 / current date in the system
    # message" line is dropped -- v2 injects no current date.
    assert "2021" not in instr


def test_compose_cwyd_instructions_appends_guardrail_once() -> None:
    """`compose_cwyd_instructions` emits the body first and the fixed
    guardrail once, last, so the non-negotiable rules have last-word
    precedence and appear exactly once."""
    composed = compose_cwyd_instructions("BODY")
    assert composed.startswith("BODY")
    assert composed.endswith(CWYD_GUARDRAIL)
    assert "BODY" in composed
    # Guardrail appears exactly once (suffix only), never duplicated.
    assert composed.count(CWYD_GUARDRAIL) == 1


def test_resolve_cwyd_instructions_none_matches_default() -> None:
    """The shared composition seam returns the built-in default,
    byte-identical to `CWYD_AGENT.instructions`, when no operator
    override is supplied -- so the default path is unchanged and only
    the override path is affected (BUG-0031)."""
    assert resolve_cwyd_instructions(None) == CWYD_AGENT.instructions


def test_resolve_cwyd_instructions_blank_override_falls_back_to_default() -> None:
    """An empty or whitespace-only override is treated as 'clear --
    use the default body', matching `_resolve_definition`'s
    strip-check, so it resolves to the same wrapped default."""
    for blank in ("", "   ", "\n\t  "):
        assert resolve_cwyd_instructions(blank) == CWYD_AGENT.instructions


def test_resolve_cwyd_instructions_override_is_guardrail_wrapped() -> None:
    """A non-empty operator override becomes the persona body wrapped
    by the fixed guardrail: the body leads, the guardrail is appended
    exactly once and last. This is the invariant BUG-0031 restores on
    the langgraph path (the override previously reached langgraph
    un-wrapped)."""
    composed = resolve_cwyd_instructions("You are the operator override.")
    assert composed.startswith("You are the operator override.")
    assert composed.endswith(CWYD_GUARDRAIL)
    assert composed.count(CWYD_GUARDRAIL) == 1
    # The override body is not itself the default body.
    assert CWYD_DEFAULT_BODY not in composed


def test_resolve_cwyd_instructions_matches_compose_for_override() -> None:
    """The seam is exactly `compose_cwyd_instructions` over the chosen
    body -- no divergent wrapping -- so the agent_framework
    (`_resolve_definition`) and langgraph (effective-config) paths
    produce identical text for the same override."""
    override = "Persona body."
    assert resolve_cwyd_instructions(override) == compose_cwyd_instructions(override)


def test_cwyd_default_instructions_are_guardrail_wrapped() -> None:
    """The built-in default is itself composed through the guardrail so
    the default prompt and any operator override share one safety
    source. The guardrail is appended once, last."""
    assert CWYD_AGENT.instructions.endswith(CWYD_GUARDRAIL)
    assert CWYD_AGENT.instructions.count(CWYD_GUARDRAIL) == 1
    # The body leads; the guardrail does not prefix the composed prompt.
    assert not CWYD_AGENT.instructions.startswith(CWYD_GUARDRAIL)


def test_cwyd_default_instructions_state_each_rule_once() -> None:
    """Dedup contract: the body defers to the guardrail, so the
    non-negotiable rules the guardrail owns appear exactly once in the
    composed prompt -- never duplicated or triplicated."""
    instr = CWYD_AGENT.instructions
    # The out-of-domain refusal message lives only in the guardrail.
    assert (
        instr.count(
            "The requested information is not available in the retrieved data. "
            "Please try another query or topic."
        )
        == 1
    )
    # The [doc+index] citation format is stated only in the guardrail.
    assert instr.count("[doc+index]") == 1


def test_cwyd_guardrail_states_non_negotiable_rules() -> None:
    """The guardrail carries the safety, out-of-domain refusal, and
    citation rules that must remain non-overridable."""
    assert "[doc+index]" in CWYD_GUARDRAIL
    assert (
        "The requested information is not available in the retrieved data."
        in CWYD_GUARDRAIL
    )
    # Refuse-to-modify-rules clause is present.
    assert "fixed" in CWYD_GUARDRAIL.lower()


def test_cwyd_guardrail_grounds_relevant_but_brief_documents() -> None:
    """The grounding rule directs the model to answer from relevant
    documents even when they are brief or partial (BUG-0028
    over-refusal fix), and bases the refusal on relevance rather than a
    strict "not enough information" reading that made gpt-5.1 refuse
    in-domain queries on the raw chat-completion path."""
    guardrail = CWYD_GUARDRAIL.lower()
    # Positive grounding directive is present (answer when relevant).
    assert "you **must** answer" in CWYD_GUARDRAIL
    assert "do not refuse" in guardrail
    # The refusal is relevance-based, not "enough information"-based.
    assert "enough information" not in guardrail
    assert "relevant" in guardrail


def test_cwyd_guardrail_bans_ungrounded_creative_content() -> None:
    """Softening the grounding rule must not regress the BUG-0011
    grounding guarantee: the guardrail still bans ungrounded creative
    content (a request such as "write me a poem" must not leak)."""
    guardrail = CWYD_GUARDRAIL.lower()
    assert "creative content" in guardrail
    assert "poems" in guardrail
    # The ban names more than one creative form.
    assert "stories" in guardrail or "jokes" in guardrail


def test_cwyd_default_body_drops_strict_in_domain_drag() -> None:
    """The v1 prompt-flow in/out-of-domain section ("think twice",
    "only when ... enough information", "you cannot decide") drove the
    BUG-0028 over-refusal and is replaced by a relevance-based
    answer/defer section."""
    body = CWYD_DEFAULT_BODY.lower()
    assert "think twice" not in body
    assert "enough information" not in body


def test_rai_agent_uses_classifier_pattern() -> None:
    """The reference-architecture-style RAI classifier returns exactly one token
    (`TRUE` or `FALSE`). The instructions must mention both tokens
    and instruct the model to emit one of them, otherwise the parser
    in CU-011a will mis-classify ambiguous outputs.
    """
    instr = RAI_AGENT.instructions
    assert "TRUE" in instr
    assert "FALSE" in instr
    # RAI agent has no tools -- it is a pure classifier.
    assert RAI_AGENT.tools == ()


def test_prompt_review_agent_reviews_system_prompts_not_user_messages() -> None:
    """`PROMPT_REVIEW_AGENT` gates the admin prompt-save path (BUG-0084).
    It is a separate TRUE/FALSE classifier from `RAI_AGENT`, calibrated
    to review operator-authored SYSTEM PROMPTS -- it must frame the
    input as a system prompt (not a user message) and explicitly permit
    the guardrail / refusal language a legitimate persona carries, so
    the default prompt and ordinary personas are not false-positived.
    """
    instr = PROMPT_REVIEW_AGENT.instructions
    assert PROMPT_REVIEW_AGENT.name == "prompt_review"
    # TRUE/FALSE single-token shape (same parser as `rai_check`).
    assert "TRUE" in instr
    assert "FALSE" in instr
    # Framed as a system-prompt review, NOT a user-message screen.
    assert "system prompt" in instr.lower()
    assert "not a" in instr.lower() and "chat message" in instr.lower()
    # Legitimate guardrail / refusal language is explicitly allowed --
    # the calibration that fixes the false positive on the default.
    assert "guardrail" in instr.lower()
    assert "allow" in instr.lower() or "allowed" in instr.lower()
    # Pure classifier -- no tools.
    assert PROMPT_REVIEW_AGENT.tools == ()


def test_builtin_agents_keyed_by_definition_name() -> None:
    """The lazy resolver (CU-010c) looks up by `definition.name`. If
    the dict key drifts from `.name`, agents would be created in
    Foundry under a key the resolver can never re-find.
    """
    for key, definition in BUILTIN_AGENTS.items():
        assert key == definition.name
    assert set(BUILTIN_AGENTS) == {"cwyd", "rai", "prompt_review"}
