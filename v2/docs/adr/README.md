# Architecture Decision Records (ADRs)

Architectural decisions for CWYD v2. Each ADR captures a single decision, the context that forced it, and the consequences. Format: [MADR](https://adr.github.io/madr/)-lite.

**Conventions**

- Filename: `NNNN-kebab-title.md` (4-digit, zero-padded, monotonic).
- One decision per ADR. If a follow-up changes the decision, write a new ADR that **supersedes** the old one — never edit a Status:Accepted ADR in place.
- Status values: `Proposed` · `Accepted` · `Superseded by ADR-NNNN` · `Deprecated`.
- ADRs are **read-only history** once Accepted. They are not the place to track work — that lives in [`development_plan.md`](../development_plan.md).

## Index

| # | Title | Status | Phase |
|---|---|---|---|
| [0001](0001-registry-over-factory-dispatch.md) | Generic `Registry[T]` over factory functions and `if/elif` dispatch | Accepted | 0 (foundational) |
| [0002](0002-no-key-vault-uami-rbac.md) | No Key Vault for app secrets — UAMI + RBAC + Bicep-output env vars | Accepted | 1 |
| [0003](0003-pydantic-settings-over-envhelper.md) | Pydantic `BaseSettings` (nested) replacing `EnvHelper` singleton | Accepted | 2 |
| [0004](0004-foundry-iq-no-openai-sdk-import.md) | Foundry IQ via `AIProjectClient` + `AsyncOpenAI` — no `openai` SDK import in v2 | Accepted | 2 |
| [0005](0005-credential-and-llm-singleton-via-lifespan.md) | Per-app credential + LLM provider singleton via FastAPI lifespan | Accepted | 2 |
| [0006](0006-health-endpoint-split.md) | Split `/api/health` (always 200) from `/api/health/ready` (503 on fail) | Accepted | 2 |
| [0007](0007-orchestrator-event-typed-sse-channel.md) | `OrchestratorEvent` typed SSE channel — `reasoning` separate from `answer` | Accepted | 2 |
| [0008](0008-lazy-foundry-agent-bootstrap.md) | Foundry agents bootstrapped lazily on first request, cached in app DB; supersedes CU-001a/e | Accepted | Cleanup audit batch 2 (Phase 4 prep) |
| [0009](0009-single-owner-no-separate-team-framing.md) | Single-owner v2; `development_plan.md` rows describe work by tier, not by team | Accepted | 7 (close-out) |
| [0010](0010-chronological-debt-queue-drainage.md) | `development_plan.md` §0.1 debt rows drain in chronological-creation order during end-of-phase audit | Accepted | 7 (close-out) |
| [0011](0011-frontend-model-extraction.md) | Frontend wire shapes + domain state types extracted into `src/models/<domain>.tsx` | Accepted | 7 (close-out, FE conventions refactor) |
| [0012](0012-frontend-test-folder-mirror.md) | Frontend tests live under `v2/src/frontend/tests/` mirroring the `src/` tree (no colocation) | Accepted | 7 (close-out, FE conventions refactor) |
| [0013](0013-frontend-strict-ts-and-tsx-everywhere.md) | Frontend ships strict TypeScript end-to-end with `.tsx` everywhere | Accepted | 7 (close-out, FE conventions refactor) |
| [0014](0014-frontend-ci-workflow.md) | Frontend CI workflow (lint + typecheck + vitest) hard-gates the strict TS posture | Accepted | 7 (close-out, FE conventions refactor follow-up) |
| [0015](0015-frontend-path-alias-cross-folder-imports.md) | Frontend cross-folder imports go through the `@/*` path alias, enforced by ESLint `import/no-relative-parent-imports` | Accepted | 7 (close-out, FE conventions refactor follow-up) |
| [0016](0016-agent-framework-foundry-iq-tas27-parity-review.md) | Agent Framework + Foundry IQ implementation review; TAS27 parity matrix and refactor path | Superseded by ADR-0017 | 8 prep (runtime parity audit) |
| [0017](0017-agent-framework-foundry-pinned-dependency-policy.md) | Agent Framework + Foundry pinned dependency policy; supersedes ADR 0016 for runtime version governance | Accepted | 8 prep (runtime parity hardening) |
| [0018](0018-monitoring-default-on-and-appi-rbac.md) | Monitoring default-on for deployed envs + `Monitoring Metrics Publisher` RBAC for UAMI on AppI | Accepted | 7 (close-out, observability gap) |
