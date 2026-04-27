# ADR 0001 — Generic `Registry[T]` over factory functions and `if/elif` dispatch

- **Status**: Accepted
- **Date**: 2026-04-21
- **Phase**: 0 (foundational; precedes Phase 2 provider work)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

CWYD v1 dispatches between four orchestrators (OpenAI Functions, Semantic Kernel, LangChain, Prompt Flow) and two databases (Cosmos DB, PostgreSQL) using a mix of:

1. Module-level `if/elif` chains over a config string (`if orchestrator_type == "semantic_kernel": ...`), often duplicated across `code/backend/`.
2. Hand-rolled factory functions (`get_orchestrator()`, `database_factory.py`) that lazy-import provider classes inside function bodies to avoid loading every dependency.
3. Conditional imports keyed on environment variables at module top-level.

The result is well-known: adding a new orchestrator or database backend requires touching ≥5 files, the dispatch labels drift from the config strings they're matched against, and a customer fork cannot add a provider without patching the upstream tree.

v2 has **seven** swappable concerns to wire (credentials, llm, embedders, parsers, search, chat_history, orchestrators) — three more than v1. Repeating the v1 pattern would multiply the maintenance cost; we need a single, uniform plug-in mechanism shared across all domains.

Two adjacent samples — Microsoft's [Multi-Agent Custom Automation Engine](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) and [Content Generation Solution Accelerator](https://github.com/microsoft/content-generation-solution-accelerator) — both use a registry-style decorator (`@register("key")`) for their pluggable surfaces. The pattern is well-trodden and works inside FastAPI's DI.

## Decision

**All swappable concerns in v2 are implemented as a registry domain.** A single generic primitive — `Registry[T]` in [`v2/src/shared/registry.py`](../../src/shared/registry.py) — backs every domain. Each domain follows the identical 3-file recipe documented in [`development_plan.md` §3.5](../development_plan.md#35-pluggability-contract-registry-first--stated-once-referenced-from-every-phase):

```text
v2/src/providers/<domain>/
├── base.py          # Base<Domain> ABC
├── __init__.py      # Registry[T] instance + eager `from . import provider_a, provider_b`
└── provider_x.py    # @registry.register("x") class ProviderX(Base<Domain>)
```

Caller code is one line and never branches on the provider key:

```python
from providers import embedders
embedder = embedders.create(settings.database.index_store, settings=settings, llm=llm)
```

### Banned anti-patterns

These are encoded as Hard Rule #4 in [`copilot-instructions.md`](../../../.github/copilot-instructions.md):

1. **`if/elif` over provider names anywhere outside a `Registry[T]`.** Greppable: `grep -rn "if .*== .['\"]cosmosdb['\"]"` must return 0 hits in `v2/src/`.
2. **Lazy in-function imports of provider classes.** Imports happen exactly once per domain in `__init__.py`. A function body never `import`s a provider.

### Scope

Applies to: credentials, llm, embedders, parsers, search, chat_history, orchestrators.

Does **not** apply to:

- Cross-cutting helpers in `shared/tools/` (content_safety, post_prompt) — these have one implementation and are imported directly.
- Composed flows in `pipelines/` (ingestion, chat) — these compose providers but are not themselves pluggable.

## Consequences

### Positive

- **Adding a provider costs the same in every domain**: one new file + one import. No central factory to edit, no `if/elif` chain to extend, no drift between config strings and dispatch labels — the registry key *is* the config value.
- **Per-container imports**: backend imports only orchestrator/chat_history/search; functions imports only embedders/parsers/search. Heavy SDKs (`azure-ai-projects`, `langgraph`, `psycopg`) load only where used, lowering cold-start time and image size per replica.
- **Out-of-tree extensibility**: a customer fork can drop `providers/embedders/customer_aoai.py` with `@register("customer_aoai")` and select it via env var — no upstream patch required.
- **One greppable rule** to enforce in code review (Hard Rule #4) instead of N domain-specific patterns.

### Negative

- **Eager imports in `__init__.py`** mean every provider in a domain is loaded the moment the domain module is touched, even if only one will be used. Mitigated by per-container imports (backend doesn't import `providers/parsers/`, so PDF parser cost is paid only by functions).
- **One layer of indirection** between caller and concrete class. Stack traces show `registry.get(...)(...)` instead of a direct constructor call. Acceptable cost for the uniformity.
- **Decorator-based registration is implicit**. A misspelled `@register("foundry-iq")` vs `@register("foundry_iq")` only fails at `create(...)` time. Mitigated by an integration test per domain that asserts the expected keys are registered.

### Neutral

- `Registry[T]` is intentionally minimal: a typed `dict[str, T]` plus `register(key)` decorator and `get(key)` lookup. No lifecycle hooks, no priorities, no fallback chains. If we need any of those later, they go on the specific domain's `create(...)` function — not on the primitive.

## Alternatives considered

1. **Keep v1's hand-rolled factory functions per domain.** Rejected: doesn't scale to 7 domains, doesn't fix the drift problem, doesn't enable out-of-tree extensions.
2. **Use `pluggy`** (the pytest plugin framework). Rejected: heavyweight for our needs (we have one impl per key, not multiple subscribers), introduces a third-party dependency for a 30-line primitive.
3. **`importlib.metadata` entry-points.** Rejected: requires installing every provider as a separately-packaged distribution, hostile to monorepo development and to local Docker builds.
4. **Service-locator container** (e.g., `dependency-injector`, `punq`). Rejected: solves a problem we don't have (full IoC graph wiring); FastAPI's `Depends(...)` already handles request-scoped DI and the registry handles configuration-driven selection.

## References

- [`v2/src/shared/registry.py`](../../src/shared/registry.py) — the primitive (≈30 lines).
- [`v2/tests/shared/test_registry.py`](../../tests/shared/test_registry.py) — 11 tests covering register, duplicate keys, missing keys, generic typing.
- [`development_plan.md` §3.5](../development_plan.md#35-pluggability-contract-registry-first--stated-once-referenced-from-every-phase) — the recipe + the 3-step "how to add new tech" table.
- [`copilot-instructions.md` Hard Rule #4](../../../.github/copilot-instructions.md) — enforcement rule.
- MACAE registry pattern: <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>.
- CGSA plug-and-play surface: <https://github.com/microsoft/content-generation-solution-accelerator>.
