# ADR 0017 — Agent Framework + Foundry pinned dependency policy

- **Status**: Accepted
- **Date**: 2026-06-04
- **Phase**: Phase 8 prep (runtime parity hardening)
- **Pillar**: Stable Core (backend orchestration/runtime contracts)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: [ADR 0016](0016-agent-framework-foundry-iq-tas27-parity-review.md). ADR 0016 remains historical context for the parity review baseline and options.

## Context

ADR 0016 established that CWYD v2 already uses Microsoft Agent Framework and Foundry IQ, but left dependency policy at broad compatible ranges while parity options were evaluated.

The user decision for this cycle is explicit: continue with Agent Framework and Agent Framework Foundry, and enforce a higher-standard, reproducible dependency posture for core runtime packages.

Range-based constraints were allowing resolver drift across critical runtime surfaces (framework, Foundry SDK edges, and FastAPI), which weakens reproducibility and complicates regression diagnosis.

## Decision

CWYD v2 adopts exact version pins for the critical Agent Framework and Foundry runtime surface in [v2/pyproject.toml](../../pyproject.toml):

- `agent-framework==1.7.0`
- `agent-framework-foundry==1.7.0`
- `azure-ai-projects==2.2.0`
- `azure-ai-agents==1.2.0b6`
- `fastapi==0.133.0`
- `openai==2.32.0`

This policy replaces the prior broad-range posture for these specific packages.

### Validation evidence

After pin hardening, the following gates were executed successfully:

1. Dependency resolution/install
   - `uv sync --project v2`
2. Strict typed backend scopes
   - `uv run --project v2 pyright v2/src/backend v2/src/functions/core`
   - Result: `0 errors, 0 warnings, 0 informations`
3. Critical provider runtime tests
   - `uv run --project v2 pytest v2/tests/backend/core/providers/orchestrators/test_agent_framework.py v2/tests/backend/core/providers/llm/test_foundry_iq.py v2/tests/backend/core/providers/agents/test_foundry.py -q`
   - Result: `55 passed` (plus 2 upstream experimental warnings emitted by `agent_framework` internals)

## Consequences

### Positive

- Reproducible installs for the most sensitive orchestration/runtime dependencies.
- Better change isolation: failures can be mapped to code changes instead of silent resolver movement.
- Policy is aligned with the user requirement for higher standards while retaining the approved Agent Framework + Foundry direction.

### Negative

- Slower dependency freshness for pinned packages; updates now require deliberate bump PRs.
- Continued intentional divergence from TAS27 exact package versions where CWYD has selected newer runtime surfaces.

### Neutral

- This ADR does not change architecture contracts (registry dispatch, SSE channels, lazy Foundry bootstrap).
- ADR 0016 remains useful as the parity review and rationale baseline.

## TAS27 parity posture after this decision

CWYD is intentionally not claiming exact TAS27 pin parity. Instead, CWYD uses a tested newer pin set while preserving architecture alignment and runtime behavior.

If exact TAS27 parity is required in the future, treat it as a dedicated compatibility effort with its own validation and rollback criteria.

## References

- [ADR 0016](0016-agent-framework-foundry-iq-tas27-parity-review.md)
- [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)
- [ADR 0008](0008-lazy-foundry-agent-bootstrap.md)
- [v2/pyproject.toml](../../pyproject.toml)
- [v2/src/backend/core/providers/orchestrators/agent_framework.py](../../src/backend/core/providers/orchestrators/agent_framework.py)
- [v2/src/backend/core/providers/llm/foundry_iq.py](../../src/backend/core/providers/llm/foundry_iq.py)
- [v2/src/backend/core/providers/agents/foundry.py](../../src/backend/core/providers/agents/foundry.py)
