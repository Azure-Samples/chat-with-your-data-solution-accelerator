<!-- markdownlint-disable-file -->
# Task Research: BUG-0054 — Event Grid `BlobCreated` poison + single-trigger ingestion

Research the open defect BUG-0054 and identify the best way to fix it that also improves the code: reduces duplicated logic, removes bad implementation, and preserves the plug-and-play / registry discipline of v2.

## Task Implementation Requests

* Understand exactly what BUG-0054 is (symptom, root cause, current partial-fix state).
* Determine the best remaining fix path (in-repo + cloud) that closes the bug.
* Specifically surface duplicated code / bad implementation in the ingestion + blob-event + batch_push path and recommend consolidation.

## Scope and Success Criteria

* Scope: the `blob_event` blueprint, `batch_push` handler, `add_url` blueprint, the backend ingestion service + queue writer, the Event Grid → queue bicep wiring, the `ingestion_trigger` flag, ADR 0028, and the BUG-0054 history. Excludes unrelated open bugs except where they gate BUG-0054 (BUG-0053, BUG-0058, BUG-0077).
* Assumptions:
  * The deployment is single-tenant (per ADR 0024).
  * v2 hard rules apply (registry dispatch, no in-function imports, StrEnum closed sets, typed-model dict returns, SDK boundary resilience).
* Success Criteria:
  * The research doc names the precise remaining steps to close BUG-0054.
  * The doc identifies concrete duplicated-code / bad-implementation sites with file + line references and a recommended consolidation.
  * One selected approach with rationale + considered alternatives.

## Outline

* What BUG-0054 is — symptom, root cause, why it is noise-only.
* The designed fix (ADR 0028, option B1) and what it replaced.
* Reconciled current state — what is implemented in-repo, what is deployed to cloud, what genuinely remains.
* The headline correction — the `blob_event` translator code is already clean; the open remainder is a cloud cutover, not bad code.
* Adjacent code-quality wins the user asked for — the 4× duplicated search-provider resolution block and the 4× parser-key derivation, with a consolidation design.
* Selected approach (split into close-out vs. optional refactor) + considered alternatives.

## TL;DR

BUG-0054 is a **stray Event Grid → queue wiring** defect, not a code-quality defect. The v1-era Event Grid subscription delivered raw `Microsoft.Storage.BlobCreated` events into the `doc-processing` queue, whose only consumer (`batch_push`) validates a strict `BatchPushQueueMessage` schema — so every event failed validation and poisoned (`doc-processing-poison` held 10, now 4, base64 envelopes). **Ingestion was never blocked** — it is poison-noise only.

The fix (ADR 0028) is **already built and green in-repo** and the `blob_event` translator was **already deployed to the cloud on 2026-06-24** (BUG-0080 unblock). What genuinely remains is a **cloud cutover**: flip `AZURE_INGESTION_TRIGGER` → `event_grid`, `azd provision`, re-validate end-to-end, drain 4 poison messages, reconcile the stale bug note. **No production code change is required to close the bug.**

The translator code the user worried about is **clean** — single typed envelope (`BatchPushQueueMessage`), single writer (`enqueue_push_message`), single typed Event Grid parser (`ParsedBlobEvent` + `BlobEventType` StrEnum). The genuine duplication lives **next to** the trigger, in the four call sites that resolve the search provider + pgvector pool; consolidating that is an **optional, separate, Hard-Rule-#10 refactor**, not part of closing BUG-0054.

## Potential Next Research

* Run the three read-only live checks (`az functionapp function list`, `azd env get-values`, `az storage message peek`) to convert the deploy-state from doc-derived to live-confirmed before any cutover.
  * Reasoning: the BUG-0054 detail block is stale; trust-but-verify before flipping the env flag.
  * Reference: subagents `bug-0054-history-adr.md`, `bug-0054-consolidation-design.md`.
* Inspect `search_skill/blueprint.py` `_execute` as a possible 4th consolidation site for the search-provider block.
  * Reasoning: surfaced during the test-seam grep; shares the pgvector-pool pattern.
  * Reference: subagent `bug-0054-consolidation-design.md` TASK B.
* Confirm the azd-env-key vs bicep-param mapping for the trigger flag (`AZURE_INGESTION_TRIGGER` setting vs `AZURE_ENV_INGESTION_TRIGGER` azd-key form in the worklogs).
  * Reasoning: a key-name mismatch at cutover would silently leave the backend on `direct_enqueue`.
  * Reference: subagent `bug-0054-consolidation-design.md` TASK A.

## Research Executed

Research was delegated to four `Researcher Subagent` passes; full notes live under `.copilot-tracking/research/subagents/2026-06-29/`:

* `bug-0054-history-adr.md` — BUG-0054 detail block, ADR 0028, worklog + dev_plan debt-queue state.
* `bug-0054-code-analysis.md` — Hard-Rule audit of the `blob_event` / `batch_push` / `add_url` / ingestion path.
* `bug-0054-infra-wiring.md` — Event Grid bicep topology, `ingestion_trigger` flag, queue-name constants, test coverage.
* `bug-0054-consolidation-design.md` — reconciled deploy state + consolidation design for the duplicated blocks.

### File Analysis

* `v2/src/functions/blob_event/event_parser.py`
  * `ParsedBlobEvent` + `ParsedBlobRef` typed models; `BlobEventType` StrEnum (`BlobCreated` / `BlobDeleted`). Single home for Event Grid envelope parsing — no duplication elsewhere. The lone `cast` is a justified Hard Rule #11(a) SDK-boundary carve-out.
* `v2/src/functions/blob_event/handler.py` (~line 71) and `blueprint.py` (lines 109-145)
  * Queue trigger classifies create → ingest / delete → `delete_by_source`; translates to a CWYD `doc-processing` message via the shared `BatchPushQueueMessage` + `enqueue_push_message`. Wrapped by `@log_queue_errors("blob_event")` (re-raise boundary, Hard Rule #14).
* `v2/src/functions/core/contracts.py` (lines 27-62)
  * `BatchPushQueueMessage` — the single frozen `doc-processing` wire contract consumed by `batch_push`. 3 construction sites (`batch_start/handler.py:61`, `blob_event/handler.py:71`, `backend/services/ingestion.py:326`) all reuse it.
* `v2/src/functions/batch_start/queue_writer.py` (lines 33-66)
  * `enqueue_push_message` — the single writer to `doc-processing`; wraps `AzureError` (Hard Rule #14).
* `v2/src/backend/core/settings.py` (lines 109, 279)
  * `IngestionTrigger(StrEnum)` = `DIRECT_ENQUEUE` / `EVENT_GRID`, hard StrEnum (no `str` arm). Default `DIRECT_ENQUEUE`.
* `v2/src/backend/services/ingestion.py` (line 301)
  * Single runtime branch on the flag: `backend_enqueues = settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE`. Under `EVENT_GRID` the backend writes the blob only and skips the `doc-processing` enqueue.
* `v2/infra/main.bicep`
  * Already in the **fix state**: both event subscriptions (`blobCreatedSubscription` ~line 2402; reuse `existingEventGridSubscription` ~line 2472) deliver to the dedicated `blob-events` queue (`queueName: blobEventsQueueName` ~line 2421), not `doc-processing`. Subscription resource *name* (`blob-created-to-doc-processing`) intentionally retained so azd does an in-place destination repoint. Flex `alwaysReady` set carries `function:batch_push` + `function:blob_event` (added 2026-06-29). `ingestionTrigger` param ~line 100, bound to the backend Container App appSetting ~line 1945; the function app deliberately omits it.

### Code Search Results

* `doc-processing` / `BlobCreated` / `BlobDeleted` / `event_grid`
  * Event Grid parsing exists only in `blob_event/event_parser.py` (no duplication). Envelope construction reuses one model + one writer.
* Search-provider + pgvector-pool + `ensure_schema` + `aclose` block (duplication)
  * `v2/src/functions/batch_push/blueprint.py:123-150`, `v2/src/functions/add_url/blueprint.py:113-141`, `v2/src/functions/blob_event/blueprint.py:109-145`, `v2/src/backend/app.py:158-184`. First three byte-identical; backend differs (app-lifespan pool from `database_client.ensure_pool()`, disabled-search gate).
* `PurePosixPath(...).suffix.lstrip(".").lower()` parser-key derivation (duplication)
  * `v2/src/functions/batch_push/blueprint.py:90`, `v2/src/functions/add_url/blueprint.py:92`, `v2/src/backend/services/ingestion.py:94` and `:217`.

### External Research

* Not required — the defect is internal infra/wiring; ADR 0028 already records the decision and rejected alternative.

### Project Conventions

* Standards referenced: `.github/copilot-instructions.md` (Hard Rules #4 registry dispatch, #10 ask-before-structural, #11 StrEnum, #14 SDK boundary, #15 typed dict returns, #17 imports-at-top, #19 durable tracking), `v2/docs/pillars_of_development.md`, `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md`, ADR 0024 (single-tenant).
* Instructions followed: `v2-functions.instructions.md`, `v2-functions-core.instructions.md`, `v2-infra.instructions.md`.

## Key Discoveries

### Project Structure

The ingestion-trigger path is a small, well-factored cluster:

* `functions/core/contracts.py` — the one cross-blueprint `doc-processing` wire model (`BatchPushQueueMessage`).
* `functions/batch_start/queue_writer.py` — the one writer (`enqueue_push_message`).
* `functions/blob_event/` — the Event Grid translator (parser + handler + blueprint) added by the fix.
* `backend/core/settings.py` — `IngestionTrigger` flag; `backend/services/ingestion.py` — the single branch.
* `infra/main.bicep` — `blob-events` queues + repointed subscriptions + `alwaysReady` set.

### Implementation Patterns

* **Single typed envelope, single writer** — no copy-pasted message assembly. 3 construction sites all reuse `BatchPushQueueMessage` + `enqueue_push_message`.
* **Single typed Event Grid parser** — `ParsedBlobEvent` / `BlobEventType` StrEnum; classification (create/delete) is data-driven, not `if/elif` over raw strings.
* **Flag-gated single trigger** — `IngestionTrigger` makes Event Grid the sole ingestion path under `EVENT_GRID`; mutually exclusive with `direct_enqueue`, so no double-enqueue at the live default.

### Hard-Rule audit — the translator path PASSES

| Rule | Check | Verdict |
|---|---|---|
| #4 registry dispatch | search/embedder/orchestrator all registry-resolved; lone `if search_key == IndexStore.PGVECTOR` is pool-kwarg injection, not provider selection | PASS |
| #11 StrEnum | `BlobEventType`, `IngestionTrigger`, `IndexStore`, `OrchestratorName` all StrEnum | PASS |
| #14 SDK boundary | `enqueue_push_message` + `upload_blob` wrap `AzureError`; `@log_queue_errors("blob_event")` re-raise boundary | PASS |
| #15 typed dict returns | `ParsedBlobEvent` / `BatchPushQueueMessage` typed models; `cast` is #11(a) carve-out | PASS |
| #17 imports-at-top | no in-function imports | PASS |

### Reconciled deploy state (the status contradiction, resolved)

The `### BUG-0054` detail block contradicts the `### BUG-0080` block. Resolution: **BUG-0080 is current; the BUG-0054 block is stale** (its 2026-06-29 touch only added the `alwaysReady` entry and never reconciled against the 06-24 deploy).

* **`blob_event` deployed to cloud? → YES** (2026-06-24, via `func ... publish --no-build --python` after the `agent-framework-core` repin fixed the Oryx/hyperlight hang; 5 → 6 functions, host Running, `/api/health` ok). Cannot have regressed since — later `azd deploy function` 403s against the locked-down storage account and `azd provision` does not redeploy code.
* **`AZURE_INGESTION_TRIGGER` flipped to `event_grid`? → NO** — still `direct_enqueue`; the flip is deferred as WI-01.
* **`doc-processing-poison` drained? → NO** — 4 historical pre-repoint messages outstanding.

### Duplication / bad-implementation sites (the user's ask)

The translator code is clean; the genuine duplication is **adjacent wiring**:

1. **Search-provider resolution block — duplicated 4× (verdict 3 + 1).** `batch_push/blueprint.py:123-150`, `add_url/blueprint.py:113-141`, `blob_event/blueprint.py:109-145` are byte-identical (resolve provider → inject `PgVectorPool` → `ensure_schema()` → `aclose()` in finally). `backend/app.py:158-184` is intrinsically different (per-process pool from `database_client.ensure_pool()`, app-lifespan scope, disabled-search gate) and stays bespoke. **Highest-value target.** Structural → Hard Rule #10.
2. **Parser-key derivation — duplicated 4×.** `PurePosixPath(name).suffix.lstrip(".").lower()` at `batch_push/blueprint.py:90`, `add_url/blueprint.py:92`, `backend/services/ingestion.py:94` & `:217`. Structural → Hard Rule #10.
3. **`_build_document` — duplicated 2×** (`batch_push/handler.py:57`, `add_url/handler.py:90`). The `add_url` copy is **documented-intentional** — leave as-is.
4. **Bicep queue-name mild duplication** — names live as both `var`s (`docProcessingQueueName`, `blobEventsQueueName`) and raw `queueServices.queues` array literals.
5. **Test coverage GAP** — no test pins the Event Grid subscription `queueName` to `blob-events`, which is the exact regression vector for BUG-0054. **Recommend adding** an infra guard test.

## Technical Scenarios

### Scenario A — Close BUG-0054 (the actual bug): cloud cutover, no code change

This is what literally closes the defect. The fix code is already in-repo and deployed.

**Requirements:**

* Backend off `direct_enqueue`; Event Grid as the single ingestion trigger; poison queue clean; stale bug note reconciled.

**Preferred Approach:**

Operator-driven cutover, in order:

1. Reconcile the stale `### BUG-0054` detail block (drop the "deploy blob_event" step — already deployed) in `v2/docs/bugs.md`.
2. `azd env set <ingestion-trigger-key> event_grid` then `azd provision` (flips the backend Container App appSetting only; the function app is unaffected). Confirm the azd-env-key → bicep-param → `AZURE_INGESTION_TRIGGER` mapping first.
3. Read-only verify the live Event Grid subscription destination is `blob-events` (not `doc-processing`).
4. Cloud end-to-end re-validation: drop a blob into `documents` (create path) and delete one (delete path); confirm ingest + de-index; confirm a clean run with no new poison (BUG-0058 prepackage workaround applied).
5. Drain the 4 `doc-processing-poison` messages.
6. Close BUG-0054; defer Option C (drop `ingestion_job_id`) as its own follow-up.

```text
v2/docs/bugs.md              # reconcile BUG-0054 detail block (docs-only)
.azure/<env>/.env            # AZURE_INGESTION_TRIGGER=event_grid (gitignored, not tracked)
# no v2/src/** change
```

**Implementation Details:** Pure ops + a docs reconcile. No production source edit. Gated only on a clean BUG-0058 deploy (prepackage workaround: `uv run python scripts/prepackage_function.py` before `azd deploy function`).

#### Considered Alternatives

* **Re-deploy `blob_event` from scratch** — rejected: it is already live (BUG-0080); a fresh `azd deploy function` 403s against the locked storage account.
* **Native Event Grid trigger (ADR 0028 option B2)** — rejected in the ADR: function access keys (no managed identity) + requires the function to exist before provisioning (breaks azd order).

### Scenario B — Optional adjacent refactor: consolidate the duplicated wiring

Directly answers "reduce duplicated code / bad implementation." **Independent of closing BUG-0054** — do not couple it to the cutover. Each helper is a Hard Rule #10 structural change needing user sign-off + a `cwyd-planner` Work Order, one unit per turn (Hard Rule #1).

**Requirements:**

* Remove the 4× search-provider block and 4× parser-key derivation without changing behavior; keep all tests green; honor the functions-vs-backend import boundary.

**Preferred Approach:**

* **Helper 1 — `resolve_search_provider`.** New module `v2/src/functions/core/search_resolution.py`:

  ```python
  async def resolve_search_provider(
      *, settings: Settings, credential: AsyncTokenCredential
  ) -> ResolvedSearch: ...
  ```

  Returns a frozen Pydantic `ResolvedSearch` (`{provider, pool_helper}`, Hard Rule #15). Serves the **three function blueprints only** (`batch_push`, `add_url`, `blob_event`); the caller keeps `aclose()` in its own `finally` so the provider stays open across handler work. `backend/app.py` stays bespoke (Site 4 excluded). Optional 5th candidate to confirm: `search_skill/blueprint.py`.

* **Helper 2 — `parser_key_for_path`.** A `backend.core` leaf (used by both functions + backend; one-way dep):

  ```python
  def parser_key_for_path(name: str) -> str:
      return PurePosixPath(name).suffix.lstrip(".").lower()
  ```

  Replaces the 4 inline derivations. Separate turn from Helper 1.

* **Test 3 — infra guard.** Add a `test_main_bicep` assertion pinning both subscription `queueName` values to `blob-events` (closes the BUG-0054 regression-vector gap). This one is **non-structural** and can land immediately.

**Implementation Details:** Route tests monkeypatch the `_execute` seam (above the helper), so `batch_push/add_url/blob_event/test_blueprint.py`, `core/test_pgvector_pool.py`, and `backend/test_app_lifespan.py` stay green unchanged; add focused unit tests for each new helper. `ensure_schema` / `aclose` are explicit (no `__aexit__`); `PgVectorPool` acquire/aclose is idempotent + single-flight, so the extraction is behavior-preserving.

#### Considered Alternatives

* **Force all 4 sites (incl. `backend/app.py`) through one helper** — rejected: the backend pool is app-lifespan-scoped from `database_client.ensure_pool()` with a disabled-search gate; folding it in would leak per-invocation semantics into the app lifespan.
* **`@asynccontextmanager` instead of a returns-struct helper** — viable, but a returns-`ResolvedSearch` struct maps 1:1 onto the current explicit `ensure_schema()` … `aclose()` lifecycle and is easier to assert in tests. Open question for the user.
* **Leave the duplication** — defensible (it is small, stable wiring), but it is real copy-paste across three blueprints and the user explicitly asked to reduce it.

## Selected Approach

**Close the bug via Scenario A (cloud cutover, zero code change); treat Scenario B as an optional, separately-planned debt-reduction sweep.** The two must not be coupled: BUG-0054 is closed by ops + a docs reconcile, and the duplication is genuine but adjacent. If the user wants the refactor, it proceeds as two Hard-Rule-#10 Work Orders (search helper first, parser-key second) plus the immediate non-structural infra guard test — each one unit per turn, test-first.

| 📊 Summary | |
|---|---|
| **Research Document** | `.copilot-tracking/research/2026-06-29/bug-0054-research.md` |
| **Selected Approach** | Scenario A closes the bug (cloud cutover + poison drain + docs reconcile, no source change); Scenario B is an optional, separately-planned dedup of the 4× search-provider block + 4× parser-key helper (both Hard Rule #10) |
| **Key Discoveries** | Translator code is clean (passes all Hard Rules); `blob_event` already deployed 2026-06-24; only the `event_grid` flip + validate + poison drain remain; stale BUG-0054 note needs reconciling; real duplication is adjacent wiring (4× + 4×); infra-test coverage gap on the subscription `queueName` |
| **Alternatives Evaluated** | 5 (re-deploy, native EG trigger, force-4-sites helper, asynccontextmanager, leave-as-is) |
| **Follow-Up Items** | 3 (live `az`/`azd` verification, `search_skill` 4th-site check, azd-key mapping confirm) |
