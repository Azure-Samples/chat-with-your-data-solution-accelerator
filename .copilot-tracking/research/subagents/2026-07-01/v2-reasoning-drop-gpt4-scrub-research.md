<!-- markdownlint-disable-file -->
# Research: Drop dedicated reasoning deployment + scrub gpt-4 across CWYD v2

Status: Complete
Date: 2026-07-01
Scope: READ-ONLY. No files were edited.

## Decisions already fixed by the user

- DROP the dedicated reasoning model deployment entirely. Remove the `o4-mini` deployment (Deprecated, retires 2026-10-16). Do NOT add `gpt-5-mini`. Collapse the reasoning slot onto the chat model `gpt-5.1` or remove it.
- SCRUB ALL `gpt-4` references across the entire `v2/**` tree.

## Search hygiene note

All inventories below EXCLUDE non-tracked / generated trees that are out of scope:
`v2/.venv/**` (third-party packages), `v2/.pytest_cache/**`, `v2/.azure/**`, `v2/.scratch/**`, and the built frontend bundle `v2/src/frontend/dist/**` + `v2/src/frontend/tsconfig.tsbuildinfo`. Those contain many `gpt-4o` / `reasoning` hits that are NOT part of the source of truth.

---

# PART 1 — Drop the dedicated reasoning deployment safely

## 1.1 Runtime consumers of the reasoning model/deployment

### Headline finding

**The dedicated reasoning deployment (`AZURE_OPENAI_REASONING_DEPLOYMENT` → `o4-mini`) is effectively DEAD in the production runtime path.** The production LLM provider is `FoundryIQ`, which OVERRIDES `complete()` and never reads `reasoning_deployment`. The reasoning panel / chain-of-thought feature is driven entirely by `supports_reasoning()` probing the **chat** deployment (`gpt_deployment` = `gpt-5.1`) and, when the chat model opts in, streaming through the Responses API. No production caller invokes `reason()` with `deployment=None`, which is the only path that reads `reasoning_deployment`.

### Trace of the two `complete()` implementations

**Production provider — `FoundryIQ.complete()`** (v2/src/backend/core/providers/llm/foundry_iq.py:672-704):

```python
chosen = self._resolve_deployment(deployment, kind="chat")   # -> gpt_deployment
if await self.supports_reasoning(chosen):                    # probes the CHAT model
    async for event in self.reason(messages, deployment=chosen):  # reason() on the CHAT deployment
        yield event
    return
async for event in super().complete(...):                    # base fallback -> chat()
    yield event
```

`FoundryIQ.complete()` NEVER references `reasoning_deployment`. It resolves the chat deployment, probes whether that chat model supports reasoning summaries, and if so streams `reason()` **with the chat deployment explicitly passed** (`deployment=chosen`). So `reason()`'s own `kind="reason"` resolution is never triggered here.

**ABC fallback — `BaseLLMProvider.complete()`** (v2/src/backend/core/providers/llm/base.py:130-136):

```python
reasoning_deployment = self._settings.openai.reasoning_deployment
chosen = deployment or self._settings.openai.gpt_deployment
if reasoning_deployment and chosen == reasoning_deployment:
    async for event in self.reason(messages, deployment=chosen):
        yield event
    return
```

This is the ONLY runtime routing that reads `reasoning_deployment`. It fires only when `chosen == reasoning_deployment` and non-empty. Since `chosen` defaults to `gpt_deployment` and no built-in agent passes `deployment=<reasoning>`, this branch is unreachable in production UNLESS `reasoning_deployment == gpt_deployment`. Moreover this is the BASE method — `FoundryIQ` (the only production provider) overrides `complete()` and reaches this only via `super().complete()` in the non-reasoning fallback, where `reasoning_deployment == chosen` is already false. Net: **dead in production.**

### `_resolve_deployment` — the reason-kind lookup

v2/src/backend/core/providers/llm/foundry_iq.py:306-320:

```python
def _resolve_deployment(self, override: str | None, *, kind: str) -> str:
    if override:
        return override
    cfg = self._settings.openai
    chosen = {
        "chat": cfg.gpt_deployment,
        "reason": cfg.reasoning_deployment,     # <-- only hit when reason(deployment=None)
        "embed": cfg.embedding_deployment,
    }[kind]
    if not chosen:
        raise RuntimeError(f"No {kind} deployment configured. ...")
    return chosen
```

The `"reason": cfg.reasoning_deployment` entry is only reached when `reason()` is called with no explicit deployment. Grep of all callers proves that never happens at runtime (see below).

### All runtime callers of `reason()` / `complete()` / `supports_reasoning()`

`grep .reason(|.complete(|.supports_reasoning(` over `v2/src/**`:

| file:line | call | passes explicit deployment? |
|---|---|---|
| v2/src/backend/core/providers/llm/base.py:136 | `self.reason(messages, deployment=chosen)` | YES (`chosen`) |
| v2/src/backend/core/providers/llm/foundry_iq.py:697 | `await self.supports_reasoning(chosen)` | probes chat |
| v2/src/backend/core/providers/llm/foundry_iq.py:700 | `self.reason(messages, deployment=chosen)` | YES (`chosen`) |
| v2/src/backend/core/providers/llm/foundry_iq.py:703 | `super().complete(...)` | fallback |
| v2/src/backend/core/providers/orchestrators/agent_framework.py:266 | `await self.llm.supports_reasoning()` | probes chat; uses Responses-API `reasoning` option on the CHAT model — does NOT touch `reasoning_deployment` |
| v2/src/backend/core/providers/orchestrators/langgraph.py:201 | `self.llm.complete(...)` | no deployment → `FoundryIQ.complete` → probes chat |

**Both orchestrators (`agent_framework`, `langgraph`) surface reasoning off the chat model.** Neither routes to the dedicated reasoning deployment. `agent_framework.py:266` sets a Responses-API `reasoning={"effort","summary"}` option on the chat client when `supports_reasoning()` is true; `langgraph.py:201` calls `complete()` which does the same via `FoundryIQ.complete`.

### Agent `deployment_attr` indirection

`AgentDefinition.deployment_attr` (v2/src/backend/core/agents/definitions.py:51,67) is a `Literal["gpt_deployment", "reasoning_deployment"]`. The provider resolves it via `getattr(settings.openai, definition.deployment_attr)`:

- v2/src/backend/core/providers/agents/base.py:247 `deployment = getattr(self._settings.openai, definition.deployment_attr)`
- v2/src/backend/core/providers/agents/foundry.py:125 same.

**All three built-in agents use `deployment_attr="gpt_deployment"`** — `CWYD_AGENT` (definitions.py:147), `RAI_AGENT` (definitions.py:163), `PROMPT_REVIEW_AGENT` (definitions.py:202). No built-in agent points at `reasoning_deployment`. The `"reasoning_deployment"` arm of the Literal is exercised ONLY by a unit test (see 1.4), never by shipping code.

### Full reasoning-consumer map (`v2/src/**`, excluding frontend rendering + comments)

| file:line | symbol / role |
|---|---|
| v2/src/backend/core/settings.py:174 | `reasoning_deployment: str = ""` (env `AZURE_OPENAI_REASONING_DEPLOYMENT`) — the setting |
| v2/src/backend/core/providers/llm/base.py:130-136 | ABC `complete()` routing on `reasoning_deployment` (dead in prod) |
| v2/src/backend/core/providers/llm/foundry_iq.py:312 | `_resolve_deployment` `"reason"` → `cfg.reasoning_deployment` (dead in prod) |
| v2/src/backend/core/agents/definitions.py:51,67 | `DeploymentAttr` Literal includes `"reasoning_deployment"` (unused by built-ins) |
| v2/src/backend/core/providers/agents/base.py:247 | `getattr(settings.openai, definition.deployment_attr)` (resolves to gpt for all built-ins) |
| v2/src/backend/core/providers/agents/foundry.py:125 | same |
| v2/src/backend/models/admin.py:117 | `reasoning_deployment: str` on the AdminConfig response model |
| v2/src/backend/routers/admin.py:144 | `reasoning_deployment=settings.openai.reasoning_deployment` populates the admin response |
| v2/src/backend/core/tools/content_safety.py:24,159 | comments referencing the `deployment_attr` indirection (no runtime read) |
| v2/src/frontend/src/models/admin.tsx:77 | `reasoning_deployment: string;` on the FE AdminConfig type |

`reason()` itself is still USED (FoundryIQ.complete calls it with the chat deployment), so `reason()` must NOT be removed — only the `reasoning_deployment` SETTING and the routing that reads it.

### post_provision (azd hook) — collected-but-unused

- v2/scripts/post_provision.py:123 — `"AZURE_OPENAI_REASONING_DEPLOYMENT"` appears only in the `SUMMARY_KEYS` display tuple (printed in the summary block).
- v2/scripts/post_provision.py:79 — stale comment "plus the Azure OpenAI reasoning model used for query planning" — INACCURATE post BUG-0023.
- The KB query-planning model is sourced from the **chat** deployment, not the reasoning one (BUG-0023 fix). See post_provision.py:354-355, 397, 435-438 which explicitly document that Foundry IQ rejects o-series reasoning models for the KB, so the chat deployment is used.

## 1.2 `OpenAISettings` reasoning field + empty-string behavior

v2/src/backend/core/settings.py:167-181:

```python
class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_", extra="ignore")
    api_version: str = ""
    gpt_deployment: str = ""
    reasoning_deployment: str = ""          # env AZURE_OPENAI_REASONING_DEPLOYMENT, default ""
    embedding_deployment: str = ""
    embedding_dimensions: int = 1536
    temperature: float = 0.0
    max_tokens: int = 1000
```

Behavior matrix:

| `AZURE_OPENAI_REASONING_DEPLOYMENT` | `FoundryIQ.complete()` (prod) | `BaseLLMProvider.complete()` (ABC) | `reason(deployment=None)` |
|---|---|---|---|
| **empty `""`** | Uses `supports_reasoning(gpt-5.1)` → reason() on the CHAT deployment. **No crash.** Never reads `reasoning_deployment`. | `if "" and ...` → False → `chat()`. **No crash.** | `_resolve_deployment(None, "reason")` → `""` → `raise RuntimeError("No reason deployment configured")`. BUT no production caller hits this. |
| **equal to `gpt-5.1`** | Identical to empty case — uses `supports_reasoning(gpt-5.1)`; never reads `reasoning_deployment`. | `chosen == reasoning_deployment` → routes to `reason()` (only matters for the base provider, which prod does not use directly). | resolves to `gpt-5.1`. |
| **different (`o4-mini`, today)** | Identical to empty case; `reasoning_deployment` never read. | never fires (`chosen` = gpt, ≠ reasoning). | resolves to `o4-mini`. |

**Conclusion:** empty `""` is completely safe for the production runtime. The only code that would `raise` on empty is `reason(deployment=None)`, which no production caller invokes. Pointing it at `gpt-5.1` is also safe and equivalent at runtime.

## 1.3 Safe collapse strategy — recommendation

Two viable options; the reasoning FEATURE (chain-of-thought panel) is PRESERVED under both because `gpt-5.1` emits reasoning summaries via the Responses API probe (`supports_reasoning`).

### Option (a) — Keep the env var, point it at `gpt-5.1` (minimal footprint)

Infra-only change; zero `src` / test changes. Leaves a redundant env var + admin field whose value now duplicates `gpt_deployment` and is never consumed by the prod path.

### Option (b) — Remove the reasoning env var + field entirely (RECOMMENDED)

Aligns with the repo's debt-reduction mandate (Hard Rule #9 + user "reduce code debt as you go"): the field is dead in production. Bigger change surface; MUST be sequenced as multiple one-unit-per-turn edits (Hard Rule #1) with a test in each turn. `reason()` STAYS (change it to resolve the chat deployment when no override is passed).

**Recommendation: Option (b) — full removal**, sequenced across units. If a single low-risk infra-only turn is preferred, fall back to Option (a) as an interim.

### Exact edit sites for Option (b) — full removal

**Infra — `v2/infra/main.bicep`:**

| line | current | action |
|---|---|---|
| 69 | `'OpenAI.GlobalStandard.o4-mini,50'` (quota `usageName` metadata) | remove this array entry |
| 122 | `@description(... chat + reasoning + embedding ...)` for `existingOpenAiName` | reword: drop "reasoning" |
| 160-161 | `@description('Optional. Reasoning model deployment name ...')` + `param reasoningModelName string = 'o4-mini'` | remove param + description |
| 163-164 | `@description('Optional. Reasoning model version.')` + `param reasoningModelVersion string = '2025-04-16'` | remove |
| 170-171 | `@description('Optional. SKU for the reasoning model deployment.')` + `param reasoningModelDeploymentType string = 'GlobalStandard'` | remove |
| 174-175 | `@description('Optional. Token capacity for the reasoning model.')` + `param reasoningModelCapacity int = 50` | remove |
| 551 | comment "chat/reasoning/embedding deployments" | reword |
| 571-584 | the reasoning deployment block inside the `deployments:` array (new-account path) — object `{ name: reasoningModelName ... }` | remove the whole object |
| 654 | comment "The chat + reasoning deployments are added ..." | reword |
| 681-699 | `resource existingOpenAiReasoningDeployment '...deployments@2024-10-01' = if (useExistingOpenAi) { ... dependsOn: [existingOpenAiGptDeployment] }` (existing-account path) | remove the whole resource |
| 708 | comment "(chat, reasoning, embedding)" | reword |
| 1881 | `{ name: 'AZURE_OPENAI_REASONING_DEPLOYMENT', value: reasoningModelName }` (backend Container App env) | remove this env entry |
| 2563 | `@description('... chat + reasoning + embedding deployments ...')` (endpoint output) | reword |
| 2581-2582 | `@description('Deployment name of the o-series reasoning model ...')` + `output AZURE_OPENAI_REASONING_DEPLOYMENT string = reasoningModelName` | remove output + description |

Note: the Function App settings do NOT reference `AZURE_OPENAI_REASONING_DEPLOYMENT` (grep of `v2/src/functions/**` for `REASONING` = empty; only the backend Container App at line 1881). Only 2 `AZURE_OPENAI_REASONING_DEPLOYMENT` occurrences in bicep (1881 env, 2582 output).

**Infra params — `v2/infra/main.parameters.json`:** lines 35-46 — remove the four `reasoningModel*` param blocks:
- 35-37 `reasoningModelName` → `${AZURE_ENV_REASONING_MODEL_NAME=o4-mini}`
- 38-40 `reasoningModelVersion` → `${AZURE_ENV_REASONING_MODEL_VERSION=2025-04-16}`
- 41-43 `reasoningModelDeploymentType` → `${AZURE_ENV_REASONING_MODEL_SKU=GlobalStandard}`
- 44-46 `reasoningModelCapacity` → `${AZURE_ENV_REASONING_MODEL_CAPACITY=50}`

**Infra params — `v2/infra/main.waf.parameters.json`:** identical block at lines 35-46 — remove the same four `reasoningModel*` params (same values).

**Settings — `v2/src/backend/core/settings.py`:** line 174 — remove `reasoning_deployment: str = ""`.

**LLM base — `v2/src/backend/core/providers/llm/base.py`:** lines 130-140 — remove the `reasoning_deployment` routing branch in `complete()`; update the docstring at 105-129 (drop the "matches reasoning_deployment" routing rule). `complete()` then always delegates to `chat()` for the base provider.

**FoundryIQ — `v2/src/backend/core/providers/llm/foundry_iq.py`:**
- line 312 — remove `"reason": cfg.reasoning_deployment,` from the `_resolve_deployment` dict.
- In `reason()` (line ~518, `model = self._resolve_deployment(deployment, kind="reason")`) — change `kind="reason"` → `kind="chat"` so a bare `reason()` defaults to the chat deployment. All current callers pass an explicit deployment, so behavior is unchanged.

**Agent definitions — `v2/src/backend/core/agents/definitions.py`:** line 51 — narrow `DeploymentAttr = Literal["gpt_deployment", "reasoning_deployment"]` → `Literal["gpt_deployment"]` (or remove the `deployment_attr` field entirely, larger change — see Hard Rule #10 before removing the field). Line 67 default `= "gpt_deployment"` unchanged.

**Admin response model — `v2/src/backend/models/admin.py`:** line 117 — remove `reasoning_deployment: str`.

**Admin router — `v2/src/backend/routers/admin.py`:** line 144 — remove `reasoning_deployment=settings.openai.reasoning_deployment,`.

**Frontend model — `v2/src/frontend/src/models/admin.tsx`:** line 77 — remove `reasoning_deployment: string;`.

**post_provision — `v2/scripts/post_provision.py`:** line 123 — remove `"AZURE_OPENAI_REASONING_DEPLOYMENT"` from `SUMMARY_KEYS`; line 79 — fix the stale comment (query planning uses the chat model, not the reasoning model).

**Tracked local env — `v2/.env`:** lines 12,15,18,19,24 reference the reasoning model. Line 17 `AZURE_OPENAI_GPT_DEPLOYMENT=gpt-5.1`, line 19 `AZURE_OPENAI_REASONING_DEPLOYMENT=o4-mini`. Remove line 19 (and the comment 18); reword comments 12/15/24. (Verify `v2/.env` is gitignored per repo convention — if tracked, it must not carry env-specific values per Hard Rule #18.)

**Docs — `v2/docs/admin_runtime_config.md`:** line 45 — the `reasoning_deployment` row in the AdminConfig field table — remove.

### Edit sites for Option (a) — keep env, point at gpt-5.1 (interim fallback)

- `v2/infra/main.bicep`: remove the o4-mini deployment objects (lines 571-584 and resource 681-699), remove the quota entry (line 69), and either (i) set `param reasoningModelName string = gptModelName`, or (ii) change the backend env at line 1881 + output at 2582 to `value: gptModelName`. Keep the `AZURE_OPENAI_REASONING_DEPLOYMENT` env/output pointing at `gpt-5.1`.
- No `src`, no test, no admin changes.
- Downside: dead env var + admin field remain, duplicating `gpt_deployment`.

## 1.4 Tests that assert reasoning routing / o-series behavior (breakage flags)

### WILL break under Option (b) (need edits, intent preservable):

| file:line | assertion | why it breaks / fix |
|---|---|---|
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:338-388 `test_reason_routes_to_reasoning_deployment_and_streams` | calls `provider.reason([...])` (NO deployment) and asserts `call.kwargs["model"] == "o4-mini"` (line 361) | This is the ONLY test that exercises `reason(deployment=None)` → `kind="reason"` → `reasoning_deployment`. If `reason()` is changed to `kind="chat"`, the resolved model becomes the chat fixture (`gpt-4o`/→`gpt-5.1`). Streaming-intent (reasoning + answer events) preserved; update the model literal + test name. |
| v2/tests/backend/core/providers/agents/test_base.py:318-338 `test_cold_start_uses_reasoning_deployment_when_definition_says_so` | builds `AgentDefinition(deployment_attr="reasoning_deployment")` and asserts `create_version...definition.model == "o4-mini"` | If `reasoning_deployment` is removed from settings AND from the `DeploymentAttr` Literal, this test cannot construct the definition. It tests the generic `deployment_attr` indirection; either delete it (no built-in uses reasoning) or re-point it at another settings attr. Helper `_make_settings` also sets `settings.openai.reasoning_deployment = "o4-mini"` at line 194 — remove. |
| v2/tests/backend/test_admin.py:245,391,400 | config-field list includes `"reasoning_deployment"` (245); `reasoning_deployment="o3-mini"` (391); `assert body["reasoning_deployment"] == "o3-mini"` (400) | AdminConfig no longer carries the field → remove these. Helper at 83/118 also injects `reasoning_deployment`. |
| v2/tests/backend/core/test_settings.py:52 | `"AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini"` env fixture | remove fixture entry (no assertion on it beyond load). |
| v2/tests/frontend/api/admin.test.tsx:49 + v2/tests/frontend/AppNavigation.test.tsx:35 | `reasoning_deployment: "gpt-5"` fixture on the AdminConfig mock | remove field from FE fixtures once the model drops it. |

### Reference `reasoning_deployment` env fixture but do NOT assert routing (low-risk, remove the env line):

- v2/tests/backend/core/providers/embedders/test_azure_openai.py:30 — `"AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini"` (env fixture only).
- v2/tests/functions/{add_url,batch_push,batch_start,blob_event,search_skill}/test_blueprint.py — each has `"AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini"` in the env fixture (lines 44/50/45/53/45). Harmless once the field is gone (settings ignores extra env), but should be cleaned.
- v2/tests/scripts/test_post_provision.py:219 — `monkeypatch.setenv("AZURE_OPENAI_REASONING_DEPLOYMENT", "o4-mini")` — remove alongside the `SUMMARY_KEYS` change.

### Routing tests that use the literal `o4-mini` but are mock-driven (intent NOT tied to `reasoning_deployment` setting):

These mock `supports_reasoning` directly, so they exercise `complete()` routing regardless of the setting. Only the literal + test names/docstrings go stale:

- v2/tests/backend/core/providers/llm/test_foundry_iq.py:40 (`AZURE_OPENAI_REASONING_DEPLOYMENT` env fixture), 567-599 `test_complete_routes_to_reason_when_deployment_matches_reasoning` (uses `deployment="o4-mini"`), 601-631 `test_complete_routes_to_reason_when_default_chat_equals_reasoning` (sets `AZURE_OPENAI_GPT_DEPLOYMENT="o4-mini"`), 633-665 `test_complete_routes_to_chat_when_no_reasoning_deployment_configured` (deletes the env var). These keep passing functionally (mock drives routing) but reference `o4-mini` / `reasoning_deployment` in names, docstrings, and literals — update for consistency.

### NOT affected (supports_reasoning ABC default):

- v2/tests/backend/core/providers/llm/test_base.py:70-84 `test_supports_reasoning_defaults_to_false*` — exercise the ABC `supports_reasoning() == False` default; independent of `reasoning_deployment`. No change.

---

# PART 2 — Full gpt-4 scrub inventory

## 2.1 Complete inventory (first-party tree only)

Case-insensitive search for `gpt-4|gpt4|gpt 4` (matches `gpt-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, etc.) across `v2/**`, excluding `.venv` / `.pytest_cache` / `.azure` / `.scratch` / `dist` / `tsbuildinfo`.

### Category A — production source `v2/src/**` (2 lines; both comments/docstrings)

| file:line | literal | note |
|---|---|---|
| v2/src/backend/core/providers/llm/foundry_iq.py:659 | `gpt-4o` | docstring example: "the deployment is a non-reasoning model (e.g. gpt-4o)" |
| v2/src/backend/core/providers/llm/registry.py:17 | `gpt-4o` | module docstring usage example `deployment="gpt-4o"` |

### Category B — infra / config `v2/infra/**` + `v2/azure.yaml` + `.env*` + `docker*` (0 gpt-4)

- `v2/infra/**` — NO gpt-4 (uses `gpt-5.1`, verified). ✓
- `v2/azure.yaml` — NO gpt-4. ✓
- `v2/docker/**` — NO gpt-4. ✓
- `v2/.env` — NO gpt-4 (has `gpt-5.1` at line 17 and `o4-mini` at line 19; both out of the gpt-4 family). Reasoning refs handled in Part 1.

### Category C — tests `v2/tests/**` (43 lines)

Sub-flag `[R]` = assertion is tied to model-routing / capability behavior (fixture literal AND assertion must change together to preserve meaning).

| file:line | literal | note |
|---|---|---|
| v2/tests/backend/core/providers/agents/test_base.py:190 | `gpt-4o-mini` | `_make_settings(deployment=...)` default |
| v2/tests/backend/core/providers/agents/test_base.py:296 | `gpt-4o-mini` | settings fixture |
| v2/tests/backend/core/providers/agents/test_base.py:308 | `gpt-4o-mini` | `[R]` `assert prompt_definition.model == "gpt-4o-mini"` |
| v2/tests/backend/core/providers/agents/test_base.py:324 | `gpt-4o-mini` | settings fixture |
| v2/tests/backend/core/providers/agents/test_base.py:561 | `gpt-4o-mini` | settings fixture |
| v2/tests/backend/core/providers/agents/test_base.py:574 | `gpt-4o-mini` | `[R]` `assert record.deployment == "gpt-4o-mini"` |
| v2/tests/backend/core/providers/embedders/test_azure_openai.py:28 | `gpt-4o` | `AZURE_OPENAI_GPT_DEPLOYMENT` env fixture |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:38 | `gpt-4o` | `AZURE_OPENAI_GPT_DEPLOYMENT` env fixture (drives most assertions below) |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:151 | `gpt-4o` | `[R]` `assert call.kwargs["model"] == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:171 | `gpt-4o-mini` | explicit deployment override |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:176 | `gpt-4o-mini` | `[R]` `assert call.kwargs["model"] == "gpt-4o-mini"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:532 | `gpt-4o` | `[R]` `assert ...["model"] == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:758 | `gpt-4o` | comment |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:761 | `gpt-4o` | `[R]` `provider.supports_reasoning.assert_awaited_once_with("gpt-4o")` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:763 | `gpt-4o` | `[R]` `assert call.kwargs["model"] == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:789 | `gpt-4o` | `[R]` `provider.supports_reasoning.assert_awaited_once_with("gpt-4o")` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:893 | `gpt-4o` | `[R]` `assert record.deployment == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:928 | `gpt-4o` | `[R]` `assert record.deployment == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:981 | `gpt-4o` | `[R]` `assert record.deployment == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:1154 | `gpt-4o` | `[R]` `assert call.kwargs["model"] == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:1189 | `gpt-4o` | `[R]` `assert record.deployment == "gpt-4o"` |
| v2/tests/backend/core/providers/llm/test_foundry_iq.py:1220 | `gpt-4o` | `[R]` `assert record.deployment == "gpt-4o"` |
| v2/tests/backend/core/test_settings.py:51 | `gpt-4.1` | `AZURE_OPENAI_GPT_DEPLOYMENT` env fixture |
| v2/tests/backend/core/test_settings.py:110 | `gpt-4.1` | `[R]` `assert settings.openai.gpt_deployment == "gpt-4.1"` |
| v2/tests/backend/core/tools/test_post_prompt.py:153 | `gpt-4o` | call arg |
| v2/tests/backend/core/tools/test_post_prompt.py:154 | `gpt-4o` | `[R]` `assert llm.chat.await_args.kwargs["deployment"] == "gpt-4o"` |
| v2/tests/backend/core/tools/test_qa.py:82 | `gpt-4o` | call arg |
| v2/tests/backend/core/tools/test_qa.py:83 | `gpt-4o` | `[R]` `assert ...["deployment"] == "gpt-4o"` |
| v2/tests/backend/core/tools/test_text_processing.py:89 | `gpt-4o-mini` | call arg |
| v2/tests/backend/core/tools/test_text_processing.py:90 | `gpt-4o-mini` | `[R]` `assert ...["deployment"] == "gpt-4o-mini"` |
| v2/tests/backend/test_admin.py:81 | `gpt-4o` | helper default `gpt_deployment` |
| v2/tests/backend/test_admin.py:389 | `gpt-4o` | fixture `gpt_deployment="gpt-4o"` |
| v2/tests/backend/test_admin.py:398 | `gpt-4o` | `[R]` `assert body["gpt_deployment"] == "gpt-4o"` |
| v2/tests/backend/test_app_lifespan.py:24 | `gpt-4o` | env fixture |
| v2/tests/backend/test_health.py:172 | `gpt-4o` | env fixture |
| v2/tests/backend/test_services_health.py:27 | `gpt-4o` | env fixture |
| v2/tests/functions/add_url/test_blueprint.py:43 | `gpt-4.1` | env fixture |
| v2/tests/functions/batch_push/test_blueprint.py:49 | `gpt-4.1` | env fixture |
| v2/tests/functions/batch_start/test_blueprint.py:44 | `gpt-4.1` | env fixture |
| v2/tests/functions/blob_event/test_blueprint.py:52 | `gpt-4.1` | env fixture |
| v2/tests/functions/search_skill/test_blueprint.py:44 | `gpt-4.1` | env fixture |
| v2/tests/scripts/test_post_provision.py:152 | `gpt-4.1` | `query_planning_model_name="gpt-4.1"` |
| v2/tests/scripts/test_post_provision.py:185 | `gpt-4.1` | `[R]` `"modelName": "gpt-4.1"` (KB model assertion) |

### Category D — docs `v2/docs/**` (11 lines). `[H]` = historical / dated process record

| file:line | literal | note |
|---|---|---|
| v2/docs/plan/business-cases.md:195 | `GPT-4 Vision` | `[H]` advanced image processing feature row (plan doc) |
| v2/docs/plan/business-cases.md:214 | `GPT-4 Vision` | `[H]` pipeline description |
| v2/docs/plan/business-cases.md:273 | `GPT-4 Vision` | `[H]` file-type table |
| v2/docs/plan/modernization-plan.md:301 | `gpt-4.1` | `[H]` `model: str = "gpt-4.1"` example |
| v2/docs/plan/modernization-plan.md:443 | `gpt-4.1` | `[H]` `AZURE_OPENAI_MODEL=gpt-4.1` example |
| v2/docs/bugs.md:81 | `gpt-4o`/`gpt-5.1` | `[H]` BUG-0023 summary row (dated defect record) |
| v2/docs/bugs.md:465 | `gpt-4o, gpt-4o-mini, gpt-4.1-...` | `[H]` BUG-0023 detail (quotes the API 400 allow-list) |
| v2/docs/bugs.md:467 | `gpt-4o / gpt-4.1` | `[H]` BUG-0023 root-cause |
| v2/docs/worklog/2026-06-12.md:152 | `gpt-4o / gpt-4.1` | `[H]` dated worklog (BUG-0023) |
| v2/docs/worklog/2026-06-14.md:117 | `gpt-4o` | `[H]` dated worklog (reasoning default-off note) |
| v2/docs/worklog/2026-06-16.md:190 | `gpt-4.1` | `[H]` dated worklog (deployment inventory of the reused v1 `oai-<DATA_SUFFIX>` account) |

Also in docs (Part-1, not gpt-4): v2/docs/admin_runtime_config.md:45 `reasoning_deployment` row.

### Category E — other production (scripts) `v2/scripts/**` (2 lines; comments)

| file:line | literal | note |
|---|---|---|
| v2/scripts/post_provision.py:354 | `gpt-4o-mini, gpt-4.1` | comment listing KB-accepted chat model examples |
| v2/scripts/post_provision.py:435 | `gpt-4o-mini, gpt-4.1` | comment listing KB-accepted chat model examples |

(These two are CURRENT, correct examples of the Foundry-IQ-accepted chat-model family, not stale gpt-4 deployment references.)

## 2.2 Scrub action per category

- **A (production src, 2)** — both are docstring/comment examples. Replace `gpt-4o` → `gpt-5.1` (or a neutral phrasing like "a non-reasoning chat model"). Zero runtime impact.
- **B (infra/config, 0)** — nothing to scrub for gpt-4 (already gpt-5.1). ✓
- **C (tests, 43)** — replace fixture literals with the current chat model `gpt-5.1` (or `gpt-5.1-mini` where a "cheaper model" is being modeled, e.g. the agent-cold-start `gpt-4o-mini` fixtures). **CRITICAL:** every `[R]`-flagged line pairs a fixture with an assertion; the env-fixture literal (e.g. `AZURE_OPENAI_GPT_DEPLOYMENT` at test_foundry_iq.py:38) and ALL downstream `== "gpt-4o"` assertions must be changed to the SAME new literal in one sweep, or the test meaning changes and it fails. In `test_foundry_iq.py` a single fixture literal (line 38) drives ~13 assertions — change them together. No test intent changes if fixture + assertions move in lockstep.
- **D (docs, 11)** — all 11 are `[H]` historical/dated records. Per Hard Rule #16 (no process narrative in src) and Hard Rule #19 (durable file-based tracking — `bugs.md` and `worklog/**` are the canonical dated defect/day records), the RECOMMENDATION is: **do NOT rewrite `bugs.md` (81, 465, 467) or the `worklog/**` entries (2026-06-12:152, 06-14:117, 06-16:190)** — they are point-in-time records that accurately describe what happened (the BUG-0023 400 error literally quoted the gpt-4o/gpt-4.1 allow-list; the 06-16 worklog records the actual deployed inventory at that date). Rewriting them would falsify history. The plan docs `business-cases.md` (195/214/273 "GPT-4 Vision") and `modernization-plan.md` (301/443 `gpt-4.1`) are forward-looking planning artifacts under `docs/plan/`; they MAY be updated to the current model if the plan is still live, or left as dated planning snapshots. **User decision required** — do not assume.
- **E (scripts, 2)** — the two `post_provision.py` comments correctly list the accepted chat-model family; leave as-is or optionally lead with `gpt-5.1` in the example list. Low priority.

## 2.3 Totals

Total first-party `gpt-4`-family occurrences (excluding `.venv` / `.pytest_cache` / `.azure` / `.scratch` / `dist` / `tsbuildinfo`): **58 lines**.

| Category | Count |
|---|---|
| A — production `v2/src/**` | 2 |
| B — infra/config (`infra`, `azure.yaml`, `.env*`, `docker*`) | 0 |
| C — tests `v2/tests/**` (`[R]` routing-tied subset: 19) | 43 |
| D — docs `v2/docs/**` (all 11 historical/dated `[H]`) | 11 |
| E — other production (`v2/scripts/**`, both comments) | 2 |
| **Total** | **58** |

`.venv` third-party packages (out of scope) account for the remaining ~31 hits from the raw 89-match count.

---

# Summary / recommendations

1. **Dropping the dedicated reasoning deployment is SAFE.** It is dead in the production `FoundryIQ` path — reasoning is driven by `supports_reasoning()` on the `gpt-5.1` chat deployment via the Responses API, not by `AZURE_OPENAI_REASONING_DEPLOYMENT`. `gpt-5.1` continues to emit chain-of-thought summaries; the reasoning panel keeps working.
2. **Recommended collapse strategy: Option (b) full removal** of the `reasoning_deployment` env var + settings field + admin exposure + dead routing branches (sequenced across one-unit-per-turn edits, each with a test). Keep `reason()` (retarget its default resolution to the chat deployment). Option (a) — point the env var at `gpt-5.1` — is the minimal infra-only fallback if a single low-risk turn is preferred.
3. **Empty `AZURE_OPENAI_REASONING_DEPLOYMENT=""` never crashes the production path.** The only `raise` site is `reason(deployment=None)`, which no runtime caller invokes.
4. **gpt-4 scrub: 58 first-party lines** — A:2, B:0, C:43, D:11, E:2.
5. **Tests that WILL break under full removal:** `test_reason_routes_to_reasoning_deployment_and_streams` (test_foundry_iq.py:338), `test_cold_start_uses_reasoning_deployment_when_definition_says_so` (agents/test_base.py:318), and `test_admin.py` (245/391/400 assert `reasoning_deployment` in AdminConfig). Several env fixtures reference the var harmlessly and just need cleanup. The `[R]`-flagged gpt-4 test lines require fixture + assertion to change in lockstep.

## Clarifying questions for the user

1. **Reasoning strategy — (a) keep env var pointed at `gpt-5.1`, or (b) full removal of the field?** Research recommends (b) for debt reduction; (a) is a smaller footprint. Confirm which to execute.
2. **`deployment_attr` indirection** — under full removal, should `DeploymentAttr` be narrowed to `Literal["gpt_deployment"]` (keep the seam) or should the `deployment_attr` field be removed entirely (larger change; triggers Hard Rule #10 structural confirmation)?
3. **Historical docs (`bugs.md`, `worklog/**`, `docs/plan/**`)** — leave the 11 `[H]` gpt-4 references as dated records (recommended for `bugs.md`/`worklog`), or update the `docs/plan/**` planning snapshots to the current model?
4. **Test model literal** — replace gpt-4 test fixtures with `gpt-5.1` uniformly, and use `gpt-5.1-mini` (or similar) where the fixture models a deliberately "cheaper" agent deployment (the `gpt-4o-mini` cases)?
5. **`v2/.env`** — confirm this file is gitignored (local dev only). If tracked, it must be scrubbed of env-specific values per Hard Rule #18 regardless of this task.
