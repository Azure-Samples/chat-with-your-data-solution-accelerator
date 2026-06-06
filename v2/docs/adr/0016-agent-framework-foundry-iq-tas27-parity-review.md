# ADR 0016 — Agent Framework + Foundry IQ implementation review and TAS27 parity plan

- **Status**: Superseded by ADR-0017
- **Date**: 2026-06-04
- **Phase**: Phase 8 prep (post FE-REVIEW close)
- **Pillar**: Stable Core (backend orchestration/runtime contracts)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR is additive to [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md) and [ADR 0008](0008-lazy-foundry-agent-bootstrap.md). Superseded for dependency governance by [ADR 0017](0017-agent-framework-foundry-pinned-dependency-policy.md).

## Context

The project requested a formal review proving CWYD v2 is implemented with Microsoft Agent Framework and Foundry IQ, using MACAE branch `feature/TAS27` as the multi-agent reference baseline. The review requirement has two parts:

1. Confirm implementation evidence in CWYD v2 source.
2. Compare exact dependency/runtime parity with TAS27 and define refactor work when parity is not exact.

### Evidence: CWYD v2 uses Agent Framework and Foundry IQ

CWYD v2 implementation evidence is concrete and already live:

- Agent Framework orchestrator runtime and Foundry hosted-agent adapter:
  - [v2/src/backend/core/providers/orchestrators/agent_framework.py](../../src/backend/core/providers/orchestrators/agent_framework.py)
- Foundry IQ project client usage (`AIProjectClient`) for chat/reasoning:
  - [v2/src/backend/core/providers/llm/foundry_iq.py](../../src/backend/core/providers/llm/foundry_iq.py)
- Foundry agents provider (`AgentsClient`) and lazy bootstrap path:
  - [v2/src/backend/core/providers/agents/foundry.py](../../src/backend/core/providers/agents/foundry.py)
  - [v2/src/backend/core/providers/agents/base.py](../../src/backend/core/providers/agents/base.py)
- FastAPI dependency wiring for orchestrator/agents:
  - [v2/src/backend/dependencies.py](../../src/backend/dependencies.py)
- Dependency declarations:
  - [v2/pyproject.toml](../../pyproject.toml)

### Reference baseline: MACAE feature/TAS27

Reference branch:

- <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/tree/feature/TAS27>

Primary dependency baseline source:

- <https://raw.githubusercontent.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/feature/TAS27/src/backend/pyproject.toml>

## Decision

CWYD v2 is confirmed to be implemented using Agent Framework and Foundry IQ, but exact TAS27 parity is partial. We adopt a phased refactor plan to evaluate exact pin parity without destabilizing the active runtime.

### Parity matrix (CWYD v2 vs TAS27 exact pins)

| Package | CWYD v2 (current) | TAS27 reference | Parity status |
|---|---|---|---|
| `azure-ai-projects` | `>=2.1.0,<3.0` | `==2.1.0` | Partial (compatible range, not exact pin) |
| `agent-framework` surface | `agent-framework-core>=1.7,<2.0` + `agent-framework-foundry>=1.7,<2.0` | `agent-framework==1.6.0` + `agent-framework-foundry==1.6.0` | Divergent (CWYD is on newer split packages/range) |
| `azure-ai-agents` | `>=1.2.0b3` | `==1.1.0` | Divergent (CWYD beta track vs TAS27 GA pin) |
| `openai` | `>=2.26,<3.0` | `==2.34.0` | Partial (compatible major, not exact pin) |
| `fastapi` | `>=0.115,<1.0` | `==0.116.1` | Partial (compatible range, not exact pin) |

### Architecture alignment summary

CWYD already aligns on the core multi-agent principles used in MACAE:

- registry-driven orchestrator/provider dispatch (plug-and-play)
- typed SSE event channels (`reasoning/tool/answer/citation/error`)
- Foundry project and agents integration via Azure SDK clients

Intentional differences currently remain:

- CWYD uses a split Agent Framework package surface (`agent-framework-core` + `agent-framework-foundry`) on a newer range.
- CWYD currently carries `azure-ai-agents` beta range where TAS27 is pinned to GA `1.1.0`.

## Consequences

### Positive

- We have explicit proof that CWYD v2 is already on Agent Framework + Foundry IQ.
- We now have an auditable parity matrix and package-by-package risk framing.
- Refactor work can be executed intentionally rather than ad hoc package bumps.

### Negative

- Exact TAS27 pin parity cannot be claimed today.
- Moving from CWYD ranges to exact TAS27 pins may require API and behavior adaptation in orchestrator/provider code.
- Beta-to-GA transition risk exists for `azure-ai-agents` usage.

### Neutral

- Existing ADR constraints remain unchanged:
  - Foundry IQ access pattern from [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)
  - lazy Foundry agent bootstrap from [ADR 0008](0008-lazy-foundry-agent-bootstrap.md)

## Refactor plan (if exact TAS27 parity is required)

### R1 — Dependency pin trial branch

Create a dedicated backend parity branch and move to exact TAS27 pins for:

- `azure-ai-projects==2.1.0`
- Agent Framework package strategy chosen explicitly:
  - either TAS27 umbrella route (`agent-framework==1.6.0` + `agent-framework-foundry==1.6.0`), or
  - retain split route and document why exact TAS27 package shape is not adopted
- `azure-ai-agents==1.1.0` (GA parity trial)

### R2 — Static/type validation

Run strict checks after pin trial:

- `uv sync`
- `uv run pyright`
- targeted backend tests for orchestrator/agents/llm providers

Primary acceptance criterion: no new typing regressions around Agent Framework and Foundry client wrappers.

### R3 — Runtime contract verification

Verify conversation runtime behavior remains intact:

- SSE event channel contract unchanged (`reasoning/tool/answer/citation/error`)
- Agent Framework orchestrator still streams expected update/event mapping
- Foundry IQ `chat_stream` and reasoning paths return equivalent outcomes

### R4 — Full regression and rollback gate

Execute full backend/frontend suites and define rollback trigger:

- rollback if parity pins break orchestrator streaming semantics, Foundry agent lifecycle, or typed event contract
- retain current CWYD ranges and document divergence rationale if rollback is triggered

## References

- [v2/pyproject.toml](../../pyproject.toml)
- [v2/src/backend/core/providers/orchestrators/agent_framework.py](../../src/backend/core/providers/orchestrators/agent_framework.py)
- [v2/src/backend/core/providers/llm/foundry_iq.py](../../src/backend/core/providers/llm/foundry_iq.py)
- [v2/src/backend/core/providers/agents/foundry.py](../../src/backend/core/providers/agents/foundry.py)
- [v2/src/backend/core/providers/agents/base.py](../../src/backend/core/providers/agents/base.py)
- [v2/src/backend/dependencies.py](../../src/backend/dependencies.py)
- [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)
- [ADR 0008](0008-lazy-foundry-agent-bootstrap.md)
- MACAE TAS27 branch: <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/tree/feature/TAS27>
- TAS27 backend dependencies: <https://raw.githubusercontent.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/feature/TAS27/src/backend/pyproject.toml>
