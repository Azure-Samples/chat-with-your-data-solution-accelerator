# Extending CWYD v2 with third-party provider plugins

CWYD v2 ships an entry-point discovery pipeline so a third-party Python
package can self-register a provider against any of the eight provider
domains **without editing core code**. Drop a pip package into the
deployment, set one env var, and the new provider is live.

This document explains the contract for plugin authors and the
operator-side surface for selecting third-party plugins at runtime.

---

## 1. Provider domains

Every swappable concern in v2 lives under
`v2/src/backend/core/providers/<domain>/` and dispatches through a
`Registry[T]` instance per Hard Rule #4. Each registry calls
`backend.core.discovery.load_entry_points("cwyd.providers.<domain>")`
at import time, so any installed plugin that declares an entry point in
the matching group fires its `@registry.register("<key>")` decorator
during startup.

| Domain          | Entry-point group              | Selection mechanism                                   |
| --------------- | ------------------------------ | ----------------------------------------------------- |
| `databases`     | `cwyd.providers.databases`     | env var `AZURE_DB_TYPE`                               |
| `search`        | `cwyd.providers.search`        | env var `AZURE_INDEX_STORE`                           |
| `embedders`     | `cwyd.providers.embedders`     | internal — caller passes the key                      |
| `parsers`       | `cwyd.providers.parsers`       | internal — Functions pipeline dispatches by extension |
| `llm`           | `cwyd.providers.llm`           | internal — caller passes the key                      |
| `orchestrators` | `cwyd.providers.orchestrators` | env var `CWYD_ORCHESTRATOR_NAME`                      |
| `credentials`   | `cwyd.providers.credentials`   | internal — `select_default()` heuristic               |
| `agents`        | `cwyd.providers.agents`        | internal — caller passes the key                      |

Domains marked **"internal"** still accept third-party registrations, but
selection is not env-var driven today. Consumers ask the registry for a
key by name (`<domain>_registry.registry.get("my_key")`). If you need a
new env-var carve-out for one of those domains, propose it as a
Hard Rule #11 amendment before adding code.

---

## 2. Author a plugin (5 steps)

### Step 1 — Subclass the domain base

Each domain exposes a base class under
`v2/src/backend/core/providers/<domain>/base.py`. Your concrete class
must satisfy its async contract. The example below is a third-party
MongoDB database provider:

```python
# my_cwyd_plugin/mongodb_provider.py

from backend.core.providers.databases import registry as databases_registry
from backend.core.providers.databases.base import BaseDatabaseProvider

@databases_registry.registry.register("mongodb")
class MongoDbProvider(BaseDatabaseProvider):
    """MongoDB-backed chat-history + conversation-state provider."""

    def __init__(self, *, settings, credential):
        self._settings = settings
        self._credential = credential
        # ...connect lazily on first use

    async def get_conversations(self, user_id: str):
        ...
```

The `@register("mongodb")` decorator runs the moment the module is
imported. The registry is case-insensitive, so `"MongoDB"`, `"mongodb"`,
and `"MONGODB"` all resolve to the same entry.

### Step 2 — Declare the entry point in `pyproject.toml`

```toml
# my-cwyd-plugin/pyproject.toml

[project]
name = "my-cwyd-plugin"
version = "0.1.0"
dependencies = ["motor>=3.6"]

[project.entry-points."cwyd.providers.databases"]
mongodb = "my_cwyd_plugin.mongodb_provider"
```

The **left side** (`mongodb`) is a human label visible in plugin logs.
The **right side** is the dotted path to the module whose import fires
the `@register(...)` decorator. The label and the registered key do
**not** have to match — the registered key is whatever you pass to
`@register("...")`.

You can declare more than one plugin per domain in the same package, and
the same package can declare plugins across multiple domains:

```toml
[project.entry-points."cwyd.providers.databases"]
mongodb = "my_cwyd_plugin.mongodb_provider"
dynamodb = "my_cwyd_plugin.dynamodb_provider"

[project.entry-points."cwyd.providers.search"]
opensearch = "my_cwyd_plugin.opensearch_search"
```

### Step 3 — Install the package alongside CWYD v2

In the deployment image (or local dev environment), install the plugin
into the same Python environment as `v2/src/backend`:

```bash
uv pip install my-cwyd-plugin
```

For local development on the plugin itself, use an editable install:

```bash
uv pip install -e ./my-cwyd-plugin
```

### Step 4 — Select the plugin at runtime

For env-var-driven domains (`databases`, `search`, `orchestrators`),
set the env var to your registered key:

```bash
export AZURE_DB_TYPE=mongodb
```

For internal-selection domains, point the calling code at your key:

```python
embedder_cls = embedders_registry.registry.get("my_custom_embedder")
```

### Step 5 — Verify

Start the backend (`docker compose -f v2/docker/docker-compose.dev.yml
up` from the repo root) and tail the logs. You should see a structured
INFO entry per plugin loaded:

```
INFO backend.core.discovery: Extension plugin loaded
  operation=load_entry_point
  group=cwyd.providers.databases
  plugin_name=mongodb
  plugin_value=my_cwyd_plugin.mongodb_provider
```

If the env-var-selected key is missing from the registry, the next
`registry.get(...)` call raises `KeyError` listing every registered key
— the diagnostic includes both first-party and third-party keys.

---

## 3. Loud-failure policy

`backend.core.discovery.load_entry_points` does **not** swallow plugin
load failures. If your plugin module raises at import time, the loader
logs a structured `WARNING` and re-raises so the FastAPI lifespan halts
— exact parity with first-party side-effect imports. The startup
failure surfaces in the container logs with:

```
ERROR backend.core.discovery: Extension plugin failed to load
  operation=load_entry_point
  group=cwyd.providers.databases
  plugin_name=mongodb
  plugin_value=my_cwyd_plugin.mongodb_provider
Traceback (most recent call last):
  ...
```

This is intentional. A silently-skipped plugin would leave the operator
with an empty registry slot at request time, which is much harder to
debug than a hard fail at startup. If your plugin has optional
dependencies, guard them at *use* time (inside the provider's async
methods), not at *import* time.

---

## 4. The Hard Rule #11 registry-driven carve-out

Settings fields that select a registry key are typed as
`<FirstPartyEnum> | str` rather than the bare enum. This is the
**registry-driven carve-out** added to Hard Rule #11 on 2026-06-02 — the
enum still defines the first-party closed set, but the `str` arm of the
union lets Pydantic accept any value an operator might point at a
third-party-registered key.

In code today, these fields are:

- `DatabaseSettings.db_type: DbType | str`
- `DatabaseSettings.index_store: IndexStore | str`
- `OrchestratorSettings.name: Literal["langgraph", "agent_framework"] | str`

Internal branches still compare against the enum members
(`if value == DbType.COSMOSDB:`); the `str` arm exists only so Pydantic
admits unknown registered keys at parse time. Validation moves to the
registry boundary, where `registry.get(key)` raises `KeyError` listing
every registered key (first-party + third-party) on miss.

Domains whose selection is internal (caller passes the key) do not need
the carve-out today — their consumers already validate at the registry
boundary.

---

## 5. Cross-references

- [Hard Rule #4](../../.github/copilot-instructions.md) — registry-based
  plug-and-play dispatch.
- [Hard Rule #11](../../.github/copilot-instructions.md) — registry-driven
  carve-out for closed-set settings fields.
- [Hard Rule #14](../../.github/copilot-instructions.md) — SDK boundary
  resilience and loud-failure policy.
- `backend/core/discovery.py` — the canonical loader implementation.
- `backend/core/registry.py` — the `Registry[T]` primitive (case-insensitive
  keys, collision detection).
