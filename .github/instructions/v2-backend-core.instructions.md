---
description: "CWYD v2 backend/core conventions (registry primitive, settings, observability, types; LLM, embedders, parsers, search, chat history, orchestrators, credentials providers; ingestion + chat pipelines). Use when: editing v2/src/backend/core/**, v2/src/backend/core/providers/**, or v2/src/backend/core/pipelines/**; building an orchestrator; adding a tool; calling Foundry IQ; adding a search handler; adding an embedder; adding a chat history backend; defining the OrchestratorEvent contract; wiring async credentials."
applyTo: "v2/src/backend/core/**"
---

# v2 backend/core / Providers / Pipelines Conventions

## Layout (binding — matches dev_plan §3.4)

```
v2/src/backend/
  core/                  primitives only — registry.py, settings.py, types.py, observability.py
    providers/           registry-keyed plug-ins, one folder per domain:
                           credentials/  llm/  embedders/  parsers/
                           search/  chat_history/  orchestrators/
    pipelines/           composed flows — ingestion.py, chat.py (NOT pluggable)
    tools/               cross-cutting helpers — content_safety.py, post_prompt.py
    agents/              built-in agent definitions (data; not registry providers)
```

`backend/core/` holds cross-cutting primitives only. `backend/core/providers/` holds every swappable concern. `backend/core/pipelines/` composes providers into flows. Do not introduce subfolders under `backend/core/<domain>/` for pluggable concerns — those belong under `backend/core/providers/<domain>/`.

## Pluggability contract (registry-first)

The generic `Registry[T]` lives in `v2/src/backend/core/registry.py`. Per Hard Rule #13 in [.github/copilot-instructions.md](../copilot-instructions.md), every provider `__init__.py` is a **package marker only** (module docstring + nothing else) — the registry, eager imports, and any helpers live in a sibling `registry.py`. The recipe:

```python
# v2/src/backend/core/providers/<domain>/__init__.py  -- MARKER ONLY
"""<Domain> provider package.

Pillar: Stable Core
Phase: <n>
"""
```

```python
# v2/src/backend/core/providers/<domain>/registry.py
from backend.core.registry import Registry
from .base import Base<Domain>

registry: Registry[type[Base<Domain>]] = Registry("<domain>")

# Eager imports trigger @registry.register(...) on each concrete.
from . import provider_a, provider_b  # noqa: E402, F401
```

```python
# v2/src/backend/core/providers/<domain>/provider_a.py
from .registry import registry

@registry.register("a")
class ProviderA(Base<Domain>): ...
```

Caller code (no `create()` sugar — it added zero behavior over `Registry.get`):

```python
from backend.core.providers.<domain> import registry as <domain>_registry

instance = <domain>_registry.registry.get(settings.<key>)(**kwargs)
```

**Forbidden:** `if/elif` over provider names anywhere outside a registry; lazy `import` of provider classes inside functions; module-level client instantiation; **any runtime code in `__init__.py`** (enforced by `v2/tests/shared/test_init_files_are_marker_only.py`); `create(key, **kwargs)` factory wrappers (call `registry.get(key)(**kwargs)` directly).

## Stack rules

- **Foundry IQ only** for model + knowledge access. No `from openai import AzureOpenAI`.
- LangGraph for graph-based orchestration. No `langchain.agents.ZeroShotAgent` / `AgentExecutor` (legacy).
- Azure AI Agent Framework (`azure-ai-agents`) for managed-agent orchestration.
- All I/O is async. All clients are constructed via provider factories — no module-level instantiation.

## Orchestrator contract

`v2/src/backend/core/providers/orchestrators/base.py` defines:

```python
class OrchestratorBase(ABC):
    @abstractmethod
    async def run(self, request: ConversationRequest) -> AsyncIterator[OrchestratorEvent]: ...
```

Every concrete orchestrator (`langgraph.py`, `agent_framework.py`):

1. Inherits `OrchestratorBase`.
2. Self-registers via `@registry.register("<key>")` against the registry exposed in `backend/core/providers/orchestrators/__init__.py`.
3. Emits events on channels: `reasoning`, `tool`, `answer`, `citation`, `error`. Never inline reasoning into `answer`.
4. Pre-pipeline: content safety check on input. Post-pipeline: post-prompt formatting + content safety check on output. Both live in `v2/src/backend/core/tools/` (cross-cutting helpers, not registry providers).

## LLM provider (Foundry IQ)

- Class `FoundryIQ` in `v2/src/backend/core/providers/llm/foundry_iq.py`, registered as `@registry.register("foundry_iq")` against `backend/core/providers/llm/__init__.py`.
- Inherits `BaseLLMProvider` (`v2/src/backend/core/providers/llm/base.py`).
- Methods: `chat(...)`, `chat_stream(...)`, `embed(...)`, `reason(...)` (o-series; routes to a reasoning deployment).
- Constructor takes `AppSettings` and a `TokenCredential`. Never reads env vars directly.
- `reason()` yields `OrchestratorEvent(channel="reasoning", ...)` and `OrchestratorEvent(channel="answer", ...)` separately.

## Credentials provider

- `v2/src/backend/core/providers/credentials/managed_identity.py` registered as `"managed_identity"` (returns `DefaultAzureCredential`).
- `v2/src/backend/core/providers/credentials/cli.py` registered as `"cli"` (returns `AzureCliCredential`).
- Selected via `AppSettings.identity.client_id` presence (deployed Managed Identity has it set) or explicit setting.
- Async: prefer `azure.identity.aio.DefaultAzureCredential` for use in async clients.

## Tool registration

- Each tool in `v2/src/backend/core/tools/<name>.py` exports a `Tool` instance with `name`, `description`, `args_schema` (Pydantic), `arun(...)` async method. Tools are cross-cutting helpers (content safety, post-prompt, etc.) and are referenced directly — they are not a registry domain.
- Tools are pillar-tagged in their docstring. Most are **Stable Core**; scenario-specific ones are **Scenario Pack**.

## Search providers

- `v2/src/backend/core/providers/search/azure_search.py` (registered `"azure_search"`) and `v2/src/backend/core/providers/search/pgvector.py` (registered `"pgvector"`) implement `BaseSearch` (`v2/src/backend/core/providers/search/base.py`) with `async def search(query, top_k, filters) -> list[SearchResult]`.
- `SearchResult` is a Pydantic model in `v2/src/backend/core/types.py` with `id`, `content`, `score`, `metadata`.
- Selected at runtime via `search.create(settings.database.index_store, ...)`.

## Chat history providers

- `v2/src/backend/core/providers/databases/cosmosdb.py` (registered `"cosmosdb"`) and `v2/src/backend/core/providers/databases/postgres.py` (registered `"postgres"`) implement `BaseChatHistory` (CRUD + feedback). Async only.
- Selected at runtime via `databases.create(settings.database.db_type, ...)`.

## Settings

- Single root `AppSettings` in `v2/src/backend/core/settings.py` (Pydantic-Settings, nested per Azure service). Reads every Bicep output env var.
- Cached `get_settings()` accessor. Never read env vars directly outside this module.

## Resilience

Per `.github/copilot-instructions.md` Hard Rule #14 (SDK boundary resilience): every external SDK call crossed inside a provider, pipeline, tool, or router must be wrapped in `try/except <SDK error umbrella>` with structured logging + re-raise. This subsection is the canonical code template.

**Canonical pattern** — Azure SDK call inside a provider:

```python
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)

async def search(self, query: str, *, top: int = 10) -> list[SearchResult]:
    try:
        response = await self._client.search(query, top=top)
    except AzureError:
        logger.exception(
            "azure_search query failed",
            extra={"operation": "search", "provider": "azure_search", "top": top},
        )
        raise
    return [SearchResult.model_validate(doc) async for doc in response]
```

**SDK error umbrellas by domain** (use the narrowest umbrella that covers the SDK's exception tree, never bare `except Exception:`):

| SDK | Catch |
|---|---|
| `azure.search.documents.aio`, `azure.storage.*`, `azure.cosmos`, `azure.identity`, any `azure-*` package | `azure.core.exceptions.AzureError` |
| `openai`, `azure-ai-foundry` LLM clients | `openai.APIError` |
| `asyncpg` | `asyncpg.PostgresError` |
| `httpx` | `httpx.HTTPError` |
| Raw HTTP responses from `azure.core` | `azure.core.exceptions.HttpResponseError` (subclass of `AzureError` — only narrow if you need response-code branching) |

**Three obligations** (all three required; no exceptions):

1. **Log with `logger.exception(...)`** — captures the traceback. Never `logger.error(str(exc))` (loses traceback).
2. **Structured `extra={...}`** — always include `"operation": "<verb>"` + `"provider": "<registry_key>"`; add domain-specific snake_case keys (`top`, `index_name`, `container`, `model`, `prompt_tokens`, etc.). Operation values are descriptive verbs (`search`, `embed`, `upsert`, `fetch_blob`); they are deliberately NOT a closed set today (per Q1 in plan further considerations — kept as bare strings until central dispatch emerges).
3. **Re-raise** — bare `raise` to propagate the original; or `raise DomainError(...) from exc` if a domain-typed wrapper adds value (`__cause__` is preserved automatically with `from exc`).

**Cleanup paths own resource release, NOT error reporting.** `finally:` / `async with __aexit__` close pools, sockets, file handles. Logging stays in the `except` block. Do not log inside `finally:` unless reporting a cleanup failure that itself just occurred.

**Status checks classify failures** as `pass | degraded | fail` per `v2/src/backend/models/health.py` (`CheckStatus` / `OverallStatus` — Q12 ledger entry for the `StrEnum` migration). Router code never lets an SDK exception escape:

```python
async def _check_search(self) -> HealthCheck:
    try:
        await self._search.ping()
    except AzureError:
        logger.exception("health check failed", extra={"operation": "ping", "provider": "azure_search"})
        return HealthCheck(name="azure_search", status="fail", message="SDK error")
    return HealthCheck(name="azure_search", status="pass")
```

**Silent excepts are forbidden.** `except: pass`, `except Exception: pass`, and `except ...: ...` blocks that swallow without logging or re-raising are AST-enforced banned by `v2/tests/shared/test_no_silent_excepts.py`. The only allowed "consume" pattern is a narrow `except <Specific> as exc: logger.warning(..., extra={...})` followed by a documented fallback value — and the log line is required.

**Module-level clients are forbidden.** Long-lived SDK clients (Cosmos, Search, Storage, OpenAI) are constructed in FastAPI lifespan and injected via `Depends(...)` so cleanup is owned by the framework. Constructor-injected `_client` attributes inside providers are fine; module-level singletons are not.

## Typing standard

Per `.github/copilot-instructions.md` Hard Rule #11 (Python bullet, `Any` only at boundaries): `pyright --strict` runs on `v2/src/backend/**` + `v2/src/functions/core/**` with a 0/0/0 CI target (errors / warnings / information). This subsection is the canonical boundary classification.

**Every method has explicit return type + parameter types.** No bare generic containers (`list` → `list[Chunk]`, `dict` → `dict[str, Any]`). No implicit `Optional` (`x: str = None` → `x: str | None = None`). No missing `-> None` on side-effect-only methods.

**Boundary classification for `Any`** (the only permitted use sites):

| Class | Example | Why permitted |
|---|---|---|
| **SDK response shape kept loose** | `rows: list[dict[str, Any]] = await cur.fetch(sql)` | asyncpg/cosmos/azure-search return dicts whose key set is set by the SDK or the schema; narrowing per-call adds zero safety. |
| **Pydantic extensibility field** | `metadata: dict[str, Any] = Field(default_factory=dict)` on `Chunk`, `OrchestratorEvent`, `ConversationRequest` | Open-shape extension point is the design intent; downstream consumers narrow at use site. |
| **SDK Protocol stub kwargs** | `async def merge_or_upload_documents(self, *, documents: Sequence[Mapping[str, Any]], **kwargs: Any) -> list[Any]` | Matches the SDK's own signature so the SDK class satisfies our Protocol. `**kwargs: Any` is permitted **only** on Protocol stubs — never inside our own provider implementations. |

**Forbidden:** `Any` in internal plumbing — orchestrator state types, registry value types, provider constructor params, pipeline step return types, router request models. If you reach for `Any` outside the three classes above, declare the missing type or queue a §0.1 debt row.

**`cast(...)` and `# pyright: ignore` discipline.** Every occurrence must either:

1. Carry an inline comment naming the SDK boundary it crosses, e.g. `cast(SupportsMergeOrUploadDocuments, search_client)  # SDK SearchClient satisfies the Protocol at runtime; keyword-only Protocol signature trips pyright — see U8i-SEARCH-WRITER-PROTOCOL-DEBT`; or
2. Map to a tracked debt row in [v2/docs/development_plan.md](../../v2/docs/development_plan.md) §0.1 by ID, so the workaround has a clear lift path.

`# type: ignore` (mypy-flavored) is treated identically; `# noqa` is not a substitute.

**When an SDK boundary needs structural work** (the Protocol can't match the SDK signature, the SDK class lacks `__aenter__`, the SDK returns an untyped dict where we need a Pydantic model): queue a new §0.1 debt row with the ID prefix matching the unit that surfaced it, ship the `cast(...)` / `# pyright: ignore` workaround with the inline-comment annotation pointing at the ledger ID, and let the dedicated post-phase hardening turn lift the workaround structurally (Hard Rule #10 — structural changes need user confirmation).

## Constants — closed sets use `enum.StrEnum`

Per `.github/copilot-instructions.md` Hard Rule #11 (Python bullet): whenever ≥2 related string literals form a closed set (type discriminators, modes, channels, status values, sibling partition keys), define a `class Foo(StrEnum)` (Python 3.11+) at module scope and reference members instead of bare `_FOO = "foo"` / `_BAR = "bar"` constants.

- `StrEnum` subclasses `str`, so the wire shape is unchanged: `json.dumps(MyEnum.X) == '"x"'`, `cursor.execute("…", (MyEnum.X,))` binds as `"x"`, `dict[MyEnum.X]` indexes the same as `dict["x"]`, and `MyEnum.X == "x"` is `True`. Existing tests asserting on raw strings keep passing.
- Naming: `PascalCase` class even when the symbol is module-internal (PEP 8 — class names are `PascalCase` regardless of visibility). Prefix with `_` only if the class itself is private to the module.
- **Exempt** (stay as `UPPER_SNAKE_CASE` constants): single-value sentinels with no siblings (e.g. `_AGENT_PARTITION = "_system"`), URLs (`_POSTGRES_AAD_SCOPE`), SQL templates (`_SCHEMA_SQL`), or any literal that does not have at least one sibling forming a closed set.
- **Not affected**: Pydantic `Literal[...]` *type annotations* on model fields (`name: Literal["langgraph", "agent_framework"]`). Those are types, not runtime values; they already constrain the closed set at validation time.
- **Registry-driven carve-out (Hard Rule #11 amendment 2026-06-02)**: settings fields whose values are *keys of a `Registry[T]` provider domain* that accepts third-party plugins via `backend.core.discovery.load_entry_points("cwyd.providers.<domain>")` MAY be typed as `<MyEnum> | str` (not pure `StrEnum`). The `StrEnum` still defines the first-party well-known set and is used at every internal comparison site (`value in {MyEnum.A, MyEnum.B}`); the `str` arm exists only so Pydantic accepts a third-party-registered key supplied via env var. Validation lives at `<domain>_registry.registry.get(value)` (raises `KeyError` listing every registered key). Today: `DatabaseSettings.db_type` and `SearchSettings.index_store`. Closed-set fields with no plugin extension point (SSE channels, status enums, partition keys, etc.) remain hard `StrEnum`-only with no `str` arm.
- **In v2 today**: Cosmos item-type discriminator (`CosmosItemType.CONVERSATION | MESSAGE | AGENT`) follows this pattern; SSE channel literals (`reasoning|tool|answer|citation|error` on `OrchestratorEvent.channel`) are in the debt queue (Q12) for a directed sweep — do not refactor opportunistically.

## Runtime types — no `TYPE_CHECKING`, no `from __future__ import annotations`

Per `.github/copilot-instructions.md` Hard Rule #11 (Python bullet, **CU-013 amendment 2026-05-05**): types in v2/ are **always available at runtime**. The `if TYPE_CHECKING:` guard and `from __future__ import annotations` (PEP 563) are **banned everywhere under `v2/`** — source, tests, scripts, functions.

- All imports go in the regular import block. All annotations resolve to real symbols at class-definition time. No string-quoted forward references.
- Self-references use `typing.Self` (PEP 673, Python 3.11+) — never `"MyClass"` quoted strings.
- The invariant is enforced by [v2/tests/shared/test_no_type_checking_or_future_annotations.py](../../v2/tests/shared/test_no_type_checking_or_future_annotations.py) (AST walk over every `*.py` under `v2/`). The test fails the build if either construct surfaces.
- **Why**: lazy / quoted annotations created two recurring failure modes — (a) silent drift where the runtime symbol disappeared but the string annotation kept type-checking green; (b) Pydantic v2 + LangGraph wiring that introspects `__annotations__` at runtime and crashed on unresolved forward refs. The micro-optimisation of "avoid runtime import cost" was not worth the operational risk.
- **No exceptions.** If a genuine circular import surfaces (the only legitimate historical use case), the fix is **structural**: extract the shared type to a leaf module (e.g. [v2/src/backend/core/types.py](../../v2/src/backend/core/types.py) or a new `v2/src/backend/core/contracts/` package). This is a structural change and triggers Hard Rule #10 (ask the user first).
- **Cost note**: Azure SDK type imports (`AgentsClient`, `AsyncTokenCredential`, `ContentSafetyClient`) are already loaded at boot by the concrete provider modules — hoisting them into `base.py` adds ~0 incremental cost. Internal v2 base classes (`BaseDatabaseClient`, `BaseLLMProvider`, etc.) flow only one direction (concrete → base), so no circular risk in current architecture.


## Banned

- `from openai import …` anywhere in `v2/src/backend/core/**`.
- `semantic_kernel`, `promptflow`.
- Module-level `client = SomeClient(...)`.
- Sync DB drivers (`psycopg2` for runtime paths, blocking `azure.cosmos.CosmosClient`). `psycopg2-binary` is acceptable for migration scripts only.
- `if/elif` over provider names anywhere outside a `Registry[T]`.
- `from __future__ import annotations` and `if TYPE_CHECKING:` — see Runtime types section above (CU-013).
- In-function imports (lazy stdlib or third-party imports inside `def` / `async def` / `class` bodies, profile-conditional `if/else` import branches, `try/except ImportError` soft-dependency shims) — see Hard Rule #17 in [.github/copilot-instructions.md](../copilot-instructions.md). Enforced by `v2/tests/shared/test_imports_at_top_only.py`.
