# ADR 0005 — Per-app credential + LLM provider singleton via FastAPI lifespan

- **Status**: Accepted
- **Date**: 2026-04-26
- **Phase**: 2 (post-build review fix; supersedes the per-request DI sketch in task #14)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

The first cut of [`v2/src/backend/dependencies.py`](../../src/backend/dependencies.py) wired DI the textbook FastAPI way:

```python
def get_credential_provider(settings: SettingsDep) -> BaseCredentialProvider:
    key = credentials.select_default(settings.identity.uami_client_id)
    return credentials.create(key, settings=settings)

def get_llm_provider(
    settings: SettingsDep,
    cred_provider: CredentialProviderDep,
) -> BaseLLMProvider:
    credential = await cred_provider.get_credential()
    return llm.create("foundry_iq", settings=settings, credential=credential)
```

Two things make that wrong for CWYD:

1. **`DefaultAzureCredential.__init__` opens an `aiohttp` transport.** Every call constructs a new connection pool and IMDS/CLI probe chain. Running it per-request leaks sockets and burns CPU on each `/api/health` hit.
2. **`AIProjectClient` (Foundry, see [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)) also owns an `aiohttp` transport** and a token cache. Re-creating it per request multiplies the leak and discards the cache.

The textbook FastAPI advice — "use `Depends`, return a fresh instance" — assumes cheap constructors. These constructors aren't cheap, and worse, they own resources that need explicit `close()` / `aclose()` to release file descriptors. Per-request construction had no shutdown hook, so descriptors accumulated until the worker recycled.

We also tried caching the providers in module-level dicts inside `dependencies.py`. That worked at runtime but broke testability — pytest couldn't reset between env-var permutations without monkey-patching internal cache vars, which violates the [ADR 0003](0003-pydantic-settings-over-envhelper.md) testing seam (`get_settings.cache_clear()` should be the only reset knob).

The Microsoft [Multi-Agent Custom Automation Engine](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) sample handles this by building expensive clients once in a FastAPI `lifespan` and stashing them on `app.state`. That's the pattern we adopt.

## Decision

**Build the credential provider, the underlying `AsyncTokenCredential`, and the LLM provider exactly once per process — in the FastAPI `lifespan` startup.** Stash all three on `app.state`. DI getters read them off `request.app.state`. Lifespan shutdown closes them in reverse order.

### Lifespan (in [`v2/src/backend/app.py`](../../src/backend/app.py))

```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ... App Insights configured here if connection string set ...

    settings = get_settings()
    cred_key = credentials.select_default(settings.identity.uami_client_id)
    cred_provider = credentials.create(cred_key, settings=settings)
    credential = await cred_provider.get_credential()
    llm_provider = llm.create("foundry_iq", settings=settings, credential=credential)

    app.state.credential_provider = cred_provider
    app.state.credential = credential
    app.state.llm_provider = llm_provider

    try:
        yield
    finally:
        # Reverse-order close. Each step is best-effort -- shutdown
        # must keep going even if one underlying SDK raises.
        try:
            await llm_provider.aclose()
        except Exception:
            logger.exception("Error closing LLM provider.")
        try:
            await credential.close()
        except Exception:
            logger.exception("Error closing Azure credential.")
```

### DI (in [`v2/src/backend/dependencies.py`](../../src/backend/dependencies.py))

```python
def get_llm_provider(request: Request) -> BaseLLMProvider:
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        raise RuntimeError(
            "llm_provider missing on app.state -- lifespan did not run."
        )
    return provider
```

The `getattr(..., None)` + explicit `RuntimeError` pattern gives a clear failure when (a) tests forget to drive lifespan, or (b) someone reaches `request.app.state` before startup completes. Better than letting Starlette raise its native `AttributeError` on `app.state.foo` — the message would name `State` and not the missing key.

### Test-time short-circuit

Tests don't usually want to drive the real lifespan (it would build a real `DefaultAzureCredential`). Two patterns are supported:

1. **`dependency_overrides`** — bypasses the getter entirely, sufficient for unit tests of route handlers. Used in 9 of the 11 health-router tests.
2. **`async with _lifespan(app):`** — drives the real lifespan with monkey-patched `credentials.create` / `llm.create` so we exercise the wiring + shutdown contract end-to-end. Used by `test_lifespan_populates_app_state_and_closes_on_shutdown`.

Note: `httpx.ASGITransport` deliberately does **not** run the ASGI lifespan protocol. So driving lifespan in tests means using its async-context manager directly, not making HTTP calls through `AsyncClient`.

## Consequences

### Positive

- **Zero per-request credential / LLM-client construction.** One `aiohttp` transport per process, one token cache.
- **Deterministic shutdown.** `aclose()` is awaited even when shutdown is triggered by a SIGTERM. Aiohttp warnings ("Unclosed client session") disappear from logs.
- **Testability preserved.** `get_settings.cache_clear()` is still the only state knob tests touch on the settings side; lifespan tests use the lifespan context directly.
- **Mirrors MACAE.** Architecture readers familiar with MACAE see the same pattern in the same place.
- **DI failure mode is loud and named.** `RuntimeError("llm_provider missing on app.state -- lifespan did not run.")` points straight at the cause.

### Negative

- **`app.state` is untyped.** `app.state.credential_provider` is `Any` from FastAPI's perspective. Mitigated by typed `Depends(get_llm_provider) -> BaseLLMProvider` getters everywhere call sites consume it — the untyped surface is confined to two attribute reads in `dependencies.py`.
- **Test setup is asymmetric.** Some tests use `dependency_overrides`, others drive the lifespan context. Documented in `tests/backend/test_health.py` docstrings; the asymmetry is real but small.
- **Single LLM provider per process** means we can't trivially A/B two model deployments at request time. We don't need that today; if we ever do, we can introduce a router-level `Depends(...)` that picks from a registry of providers — without changing this ADR.

### Neutral

- **Best-effort shutdown.** Each `aclose()` / `close()` is wrapped in `try/except` because shutdown must keep going. Errors are logged via `logger.exception(...)` but don't propagate. Acceptable for resource-cleanup code; loud enough to investigate when diagnostics matter.

## Alternatives considered

1. **Per-request construction with `Depends(...)` only (the original sketch).** Rejected: the bug we fixed. Leaks aiohttp transports, no shutdown hook.
2. **Module-level cache dicts in `dependencies.py`.** Rejected: works at runtime, breaks tests (cache state survives across pytest cases), violates the single-reset-knob rule.
3. **Singleton classes wrapping each provider with `__new__` checks.** Rejected: hides the lifecycle. The lifespan + `app.state` pattern makes startup and shutdown both explicit.
4. **`functools.lru_cache` on the getter functions.** Rejected: caches across requests but still has no shutdown hook, and the cache key (FastAPI's injected types) isn't hashable in the way `lru_cache` expects.
5. **Construct in `lifespan` but inject via a custom middleware that adds providers to `request.state`.** Rejected: middleware adds latency to every request and duplicates what `request.app.state` already provides for free.

## References

- [`v2/src/backend/app.py`](../../src/backend/app.py) — `_lifespan` + `create_app`.
- [`v2/src/backend/dependencies.py`](../../src/backend/dependencies.py) — `get_credential_provider`, `get_llm_provider` reading `app.state`.
- [`v2/tests/backend/test_health.py`](../../tests/backend/test_health.py) — the `_lifespan(app)` end-to-end test plus the lifespan-not-ran failure tests.
- [ADR 0001](0001-registry-over-factory-dispatch.md) — the registry hands back a provider; lifespan owns its lifecycle.
- [ADR 0002](0002-no-key-vault-uami-rbac.md) — `DefaultAzureCredential` is the resource being managed.
- [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md) — `AIProjectClient` is the other resource being managed.
- MACAE app-state pattern: <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>.
- FastAPI lifespan docs: <https://fastapi.tiangolo.com/advanced/events/#lifespan>.
