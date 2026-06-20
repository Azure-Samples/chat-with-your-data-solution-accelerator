---
description: "CWYD v2 testing conventions and test-first contract. Use when: editing v2/tests/**, editing v2/src/**/tests/**, editing v2/tests/frontend/** (relocated frontend Vitest tree), adding a pytest test, adding a vitest/jest test, configuring fixtures, mocking Foundry IQ or Azure Search, asserting on SSE events, gating coverage, or completing the test step of the implement-then-test loop."
applyTo: "v2/tests/**,v2/src/**/tests/**"
---

# v2 Testing Conventions

## Test-first contract

Every implementation turn produces **two artifacts**: the unit and its test. The test must:

1. Exist in the matching `tests/` folder next to the unit (mirrored layout).
2. Execute (pass or fail with a meaningful assertion). No `pass` placeholders.
3. Cover at minimum: the happy path, one failure mode, one edge case.

A unit without an executing test is **not done** and may not be reported as complete.

## Python (pytest)

- `pytest` + `pytest-asyncio` + `pytest-cov`.
- Async tests: `@pytest.mark.asyncio` (set `asyncio_mode = "auto"` in `pyproject.toml`).
- HTTP backend: `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- Foundry IQ mocked via `unittest.mock.AsyncMock` injected through `Depends` overrides — never hit a real endpoint **in the default (unit) suite**. The single exception is the opt-in integration lane below, which is deselected by default and runs only against a configured environment.
- Coverage gate per new unit: the unit's lines must be ≥ 90% covered. Project-wide gate: ≥ 80%. The integration lane is excluded from coverage gating — it asserts live behavior, not line coverage.

## TypeScript (Vitest preferred, Jest for legacy)

- New tests use `vitest` + `@testing-library/react` + `msw`.
- One behavioral assertion minimum per component test.
- SSE consumers tested with a mock `EventSource` polyfill that emits scripted events.

## Fixtures

- `v2/tests/conftest.py` provides shared fixtures: `app`, `settings_override`, `mock_foundry_iq`, `mock_search_handler`, `mock_chat_history`.
- Per-area `conftest.py` allowed but must not duplicate root fixtures.

## SSE assertions

```python
async def test_conversation_emits_reasoning_then_answer(client, mock_foundry_iq):
    mock_foundry_iq.reason.return_value = scripted_events([
        ("reasoning", "thinking..."),
        ("answer", "42"),
    ])
    events = await collect_sse(client, "/api/conversation", json={"message": "x"})
    channels = [e.channel for e in events]
    assert channels == ["reasoning", "answer"]
```

## Banned in tests

- Real network calls **in the default (unit + mocked) suite** — no Azure, no `httpx` to public URLs. Real Azure data-plane calls are permitted **only** in the opt-in integration lane (see below), which is deselected by default and never runs in the standard `pytest` invocation.
- `time.sleep` — use `asyncio.sleep` or virtual time.
- Skipping tests without a reason. Unit tests that skip need a tracked issue link in the skip reason. Integration-lane tests **may** skip with a capability reason instead (e.g. `pytest.skip("requires cosmosdb mode; not configured")` / `"requires a populated v2/.env")`) so the lane self-disables on machines that lack the live environment.
- In-function imports — Hard Rule #17 in [.github/copilot-instructions.md](../copilot-instructions.md) requires all imports at module top, with zero carve-outs (tests included). Enforced by `v2/tests/shared/test_imports_at_top_only.py`.

## Integration lane (live Azure)

An opt-in lane that boots the **real** FastAPI app against **real** Azure services and asserts on real API responses (LLM answers, citations, search hits, chat-history round-trips). It complements — never replaces — the mocked unit suite.

- **Marker + location.** Mark every live test `@pytest.mark.integration` and place it under `v2/tests/integration/` (mirrors the `v2/tests/smoke/` precedent). The lane is deselected by default via `addopts = "... -m 'not smoke and not integration'"`, so the standard `pytest` run is unchanged and CI stays green without an environment.
- **Real config, loaded past the stripper.** The root `v2/tests/conftest.py` autouse fixture strips every `AZURE_*` / `CWYD_*` env for unit isolation. The lane's own `v2/tests/integration/conftest.py` re-loads the real `v2/.env` (via the already-present `python-dotenv`) and calls `get_settings.cache_clear()` **after** that stripper, then session-skips the whole lane when `v2/.env` or its required keys are absent.
- **In-process boot, no new dependency.** Construct the app with `create_app()` and run the real lifespan in-process with `async with app.router.lifespan_context(app):` (which connects credential / llm / agents / db / search to Azure), then drive it with `httpx.AsyncClient(transport=ASGITransport(app=app))`. `ASGITransport` alone does **not** run the lifespan — wrap it. Do not add `asgi-lifespan` or any harness dependency without a Hard Rule #10 approval.
- **Auth.** Exercise the real Easy Auth parser by injecting real claim headers (`x-ms-client-principal-id` + base64 `x-ms-client-principal`), not by overriding the auth dependency.
- **No environment-specific content (Hard Rule #18).** Assert on **shape and invariants** (status code, non-empty answer, citation id matches `[docN]`, the out-of-domain fallback equals the imported constant from `backend.core.agents.definitions`) — never on a real endpoint, suffix, subscription, or document title. Import fixed strings from source; do not hardcode them. The lane reads real values from the environment at runtime; it writes none into tracked files.
- **Running it.** `uv run --env-file .env pytest -m integration tests/integration -v` from `v2/`, with `az login` completed and `v2/.env` populated. Mutating tests (chat-history writes) must clean up after themselves.
