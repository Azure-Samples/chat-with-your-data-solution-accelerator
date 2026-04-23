---
description: "CWYD v2 testing conventions and test-first contract. Use when: editing v2/tests/**, editing v2/src/**/tests/**, adding a pytest test, adding a vitest/jest test, configuring fixtures, mocking Foundry IQ or Azure Search, asserting on SSE events, gating coverage, or completing the test step of the implement-then-test loop."
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
- Foundry IQ mocked via `unittest.mock.AsyncMock` injected through `Depends` overrides — never hit a real endpoint.
- Coverage gate per new unit: the unit's lines must be ≥ 90% covered. Project-wide gate: ≥ 80%.

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

- Real network calls (no Azure, no `httpx` to public URLs).
- `time.sleep` — use `asyncio.sleep` or virtual time.
- Skipping tests without a tracked issue link in the skip reason.
