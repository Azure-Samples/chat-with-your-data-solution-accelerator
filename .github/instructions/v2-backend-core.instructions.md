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

The generic `Registry[T]` lives in `v2/src/backend/core/registry.py`. Every provider domain follows the same recipe:

```python
# v2/src/backend/core/providers/<domain>/__init__.py
from backend.core.registry import Registry

registry: Registry[Base<Domain>] = Registry("<domain>")

from . import provider_a, provider_b   # eager-import triggers @register

def create(key: str, **kwargs) -> Base<Domain>:
    return registry.get(key)(**kwargs)
```

```python
# v2/src/backend/core/providers/<domain>/provider_a.py
from . import registry

@registry.register("a")
class ProviderA(Base<Domain>): ...
```

Caller code is one line — `domain.create(settings.<key>, ...)`. **Forbidden:** `if/elif` over provider names anywhere outside a registry; lazy `import` of provider classes inside functions; module-level client instantiation.

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

## Constants — closed sets use `enum.StrEnum`

Per `.github/copilot-instructions.md` Hard Rule #11 (Python bullet): whenever ≥2 related string literals form a closed set (type discriminators, modes, channels, status values, sibling partition keys), define a `class Foo(StrEnum)` (Python 3.11+) at module scope and reference members instead of bare `_FOO = "foo"` / `_BAR = "bar"` constants.

- `StrEnum` subclasses `str`, so the wire shape is unchanged: `json.dumps(MyEnum.X) == '"x"'`, `cursor.execute("…", (MyEnum.X,))` binds as `"x"`, `dict[MyEnum.X]` indexes the same as `dict["x"]`, and `MyEnum.X == "x"` is `True`. Existing tests asserting on raw strings keep passing.
- Naming: `PascalCase` class even when the symbol is module-internal (PEP 8 — class names are `PascalCase` regardless of visibility). Prefix with `_` only if the class itself is private to the module.
- **Exempt** (stay as `UPPER_SNAKE_CASE` constants): single-value sentinels with no siblings (e.g. `_AGENT_PARTITION = "_system"`), URLs (`_POSTGRES_AAD_SCOPE`), SQL templates (`_SCHEMA_SQL`), or any literal that does not have at least one sibling forming a closed set.
- **Not affected**: Pydantic `Literal[...]` *type annotations* on model fields (`name: Literal["langgraph", "agent_framework"]`). Those are types, not runtime values; they already constrain the closed set at validation time.
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
