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
