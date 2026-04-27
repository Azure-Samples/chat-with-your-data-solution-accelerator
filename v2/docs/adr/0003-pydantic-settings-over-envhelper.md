# ADR 0003 — Pydantic `BaseSettings` (nested) replacing `EnvHelper` singleton

- **Status**: Accepted
- **Date**: 2026-04-22
- **Phase**: 2 (task #10)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

CWYD v1's configuration lives in `code/backend/batch/utilities/helpers/env_helper.py` — a hand-rolled module-level singleton (`ENV_HELPER = EnvHelper()`) that:

1. Reads ~100 environment variables in `__init__`, each via `os.getenv(NAME, default)` with no validation and no type coercion.
2. Exposes them as bare attributes (`env_helper.AZURE_OPENAI_API_KEY`, `env_helper.AZURE_SEARCH_TOP_K`).
3. Mixes infrastructure-bound config (Bicep outputs) with runtime-tunable config (orchestrator selection, prompts, chunk size) on the same flat surface, so callers can't tell which is which.
4. Re-imports cause re-initialization in test contexts because the singleton is a module-level instance, not a memoized factory — so tests monkey-patch `os.environ` at import time and pray.

Costs we hit repeatedly in v1 maintenance:

- A typo in `AZURE_OPENAI_TEMPERAUTRE` returns the default silently — no error at startup, mysterious behavior at runtime.
- Numeric env vars (`AZURE_SEARCH_TOP_K`) come back as `str` and get implicitly coerced inside the call site, sometimes incorrectly.
- The flat shape forces every new field to grow the singleton by another attribute — by Phase 2 of the v1 codebase, `EnvHelper` was 600+ lines of `getattr`-style boilerplate.
- Conditional Bicep outputs (off mode emits `''`) had no schema enforcement — a missing PostgreSQL endpoint manifested as an empty string passed to `psycopg.connect("")` deep in the call stack.

v2 has 37 verified Bicep-output env vars (Phase 1.2 audit) plus a small `CWYD_*` runtime namespace. We need a config layer that:

- Catches typos and missing-required at startup, not at first use.
- Coerces types once, at the boundary.
- Groups by Azure subsystem so call sites can take only what they need.
- Plays nicely with FastAPI's `Depends(...)` and with pytest cache-clear cycles.

## Decision

**Replace `EnvHelper` with a composed Pydantic v2 `BaseSettings` tree** in [`v2/src/shared/settings.py`](../../src/shared/settings.py).

### Shape

`AppSettings` is a top-level `BaseSettings` that **composes** ~9 small per-subsystem `BaseSettings` models, one per Azure subsystem (identity, foundry, openai, search, database, storage, monitoring, network) plus an `orchestrator` namespace for runtime-tunable knobs.

```python
class AppSettings(BaseSettings):
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    foundry: FoundrySettings = Field(default_factory=FoundrySettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
```

Each per-subsystem class declares its env-var prefix via `SettingsConfigDict(env_prefix="AZURE_AI_", extra="ignore")` so the field-name → env-var mapping is explicit and discoverable.

### Two prefixes, on purpose

- **`AZURE_*`** — infrastructure-pinned. Sourced from Bicep outputs. The shape of `AppSettings` mirrors the shape of `infra/main.bicep` outputs.
- **`CWYD_*`** — runtime-tunable. Used only by the `OrchestratorSettings` namespace today (orchestrator selection, prompt overrides). Survives a redeploy when only behavior changes.

The split makes "what changes when" greppable.

### Validation

A `model_validator` on `DatabaseSettings` enforces that the side matching `AZURE_DB_TYPE` (`cosmosdb` | `postgresql`) is populated — so the cross-cutting Bicep convention "off mode emits `''`" is checked at startup, not deep in a connection-pool call.

Required fields use Pydantic defaults of `""`, with the validator turning empty-string violations into clear startup `ValidationError` messages naming the env var. Numeric fields (`temperature: float`, `max_tokens: int`) coerce once.

### Singleton via cached factory, not module-level instance

```python
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
```

Callers always go through `get_settings()`. Tests call `get_settings.cache_clear()` between env-var permutations. FastAPI uses `Depends(get_app_settings)` (a thin re-export, see [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md)).

### Banned

- Direct `os.getenv(...)` calls in v2 application code (`v2/src/backend/`, `v2/src/providers/`, `v2/src/pipelines/`, `v2/src/functions/`). All env reading goes through `AppSettings`. Greppable: `grep -rn "os\.getenv\|os\.environ\[" v2/src/` should match only `settings.py` and tests.
- Module-level `SETTINGS = AppSettings()` re-creation. The singleton is `lru_cache`d at the factory.

## Consequences

### Positive

- **Typos fail at startup** with a `ValidationError` naming the offending field. No more silent default-fallback bugs.
- **Types are correct at the boundary**. `settings.openai.max_tokens + 1` works without coercion at call sites.
- **Composed shape makes "what does this subsystem need" discoverable** — a new contributor reads `OpenAISettings` and learns the full Azure OpenAI surface in 6 fields.
- **Testability**: `get_settings.cache_clear()` is the only knob tests need. No `importlib.reload` gymnastics.
- **FastAPI native**: `Annotated[AppSettings, Depends(get_app_settings)]` flows through routers without ceremony.
- **Mirrors Bicep**: changing an output name forces a single field rename, easy to grep, easy to migrate.

### Negative

- **One Python dep** — `pydantic-settings` (already pulled in transitively by FastAPI). Cost: zero in practice.
- **Test setup must clear the cache** between env permutations (`get_settings.cache_clear()`). This is one extra autouse fixture line per test module that exercises settings; documented in [`v2/tests/conftest.py`](../../tests/conftest.py).
- **`extra="ignore"` instead of `extra="forbid"`** on per-subsystem models, so unrelated `AZURE_*` env vars (set by other tooling in the host environment) don't trip startup validation. Trade-off: a misspelled CWYD env var won't error if it accidentally collides with a known prefix. Mitigated by the typed field validator catching wrong values.

### Neutral

- The flat-attribute v1 access pattern (`env_helper.AZURE_FOO_BAR`) is gone; v2 callers write `settings.foo.bar`. This is a one-time migration cost and is enforced by code review (no `EnvHelper`-shaped helper class is allowed in v2).

## Alternatives considered

1. **Keep `EnvHelper` and bolt validation on top.** Rejected: the flat shape is itself the maintainability problem; bolting Pydantic onto a singleton doesn't fix the call-site ergonomics or the "which fields belong together" question.
2. **`dataclasses.dataclass` + manual `__post_init__` validation.** Rejected: re-implements 80% of `pydantic-settings` poorly. No env-var prefix mapping, no native nested composition, no cached factory pattern.
3. **`dynaconf` / `python-decouple`.** Rejected: heavier, less typed, and they paper over the shape problem rather than solving it. We want the source of truth to be Python types, not YAML / TOML files.
4. **One giant flat `AppSettings(BaseSettings)`** (no per-subsystem composition). Rejected: keeps the v1 ergonomics problem; makes it harder for a router to declare the narrow slice it depends on.
5. **Read settings via FastAPI `Depends(...)` only, no module-level singleton.** Rejected: providers in `v2/src/providers/` need settings during construction, and they're not necessarily inside a request scope. The cached factory works for both call paths.

## References

- [`v2/src/shared/settings.py`](../../src/shared/settings.py) — `AppSettings` and the 9 per-subsystem models.
- [`v2/tests/shared/test_settings.py`](../../tests/shared/test_settings.py) — 13 tests covering env-var coverage, type coercion, validator failure modes, cache behavior.
- [`v2/infra/main.bicep`](../../infra/main.bicep) — outputs section; the surface `AppSettings` mirrors.
- [ADR 0001](0001-registry-over-factory-dispatch.md) — the registry recipe; providers receive `AppSettings` (or a slice of it) by constructor injection.
- [ADR 0002](0002-no-key-vault-uami-rbac.md) — why no fields hold secrets.
- [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md) — how `get_settings()` plumbs into FastAPI DI.
- [`development_plan.md` §2.3 + §4 Phase 2 task #10](../development_plan.md) — the migration entry.
