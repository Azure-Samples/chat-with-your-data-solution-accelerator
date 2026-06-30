<!-- markdownlint-disable-file -->
# RPI Validation — BUG-0054 cutover-dedup, Phase 1

**Validation document**: `.copilot-tracking/reviews/rpi/2026-06-29/bug-0054-cutover-dedup-plan-001-validation.md`
**Date**: 2026-06-29
**Phase under validation**: Phase 1 — Infra regression-guard test (non-structural), Step 1.1
**Validation status**: **Partial**

## Inputs validated

| Artifact | Path |
| --- | --- |
| Implementation Plan | `.copilot-tracking/plans/2026-06-29/bug-0054-cutover-dedup-plan.instructions.md` |
| Plan Details | `.copilot-tracking/details/2026-06-29/bug-0054-cutover-dedup-details.md` (Lines 12-36) |
| Changes Log | `.copilot-tracking/changes/2026-06-29/bug-0054-cutover-dedup-changes.md` |
| Planning Log | `.copilot-tracking/plans/logs/2026-06-29/bug-0054-cutover-dedup-log.md` |
| Research (consolidated) | `.copilot-tracking/research/2026-06-29/bug-0054-research.md` |
| Research (infra-wiring) | `.copilot-tracking/research/subagents/2026-06-29/bug-0054-infra-wiring.md` (§5 "Coverage GAP") |

## Step-by-step validation

### Step 1.1 — Add `test_blob_event_subscription_targets_blob_events_queue` — Status: **Partial**

**Plan/details requirement** (details Lines 12-36):

1. Add one grep-style guard test next to `test_function_app_keeps_blob_event_always_ready` (line 202).
2. Use the module-scoped `bicep_text` fixture.
3. Assert `queueName: blobEventsQueueName` is present (destination references the `blob-events` var, not a raw `doc-processing` literal).
4. Assert both `'Microsoft.Storage.BlobCreated'` and `'Microsoft.Storage.BlobDeleted'` appear in the `includedEventTypes` filter.
5. Actionable assertion messages mirroring the sibling test's "Add … to main.bicep so …" voice.
6. No `Pillar:` header (test module, not `v2/src/**`).
7. Success criterion: `uv run pytest v2/tests/infra/test_main_bicep.py` passes; mutating the subscription `queueName` to `docProcessingQueueName` makes the test fail.
8. Plan-level success criterion (plan Success Criteria): *"The new bicep guard test fails if **either** Event Grid subscription's `queueName` regresses from `blob-events`."*

**Evidence of what was implemented:**

| Requirement | Evidence | Verdict |
| --- | --- | --- |
| Test added next to sibling | `v2/tests/infra/test_main_bicep.py` — sibling at line 202; new `def test_blob_event_subscription_targets_blob_events_queue(bicep_text: str)` at line 220 | Verified |
| Uses `bicep_text` fixture | Test param `bicep_text: str`; module-scoped fixture defined lines 28-33 | Verified |
| Asserts `queueName: blobEventsQueueName` | `test_main_bicep.py` line 233: `assert "queueName: blobEventsQueueName" in bicep_text` | Verified (positive presence only — see DR-A) |
| Asserts both event types | `test_main_bicep.py` lines 239-249: loop over `'Microsoft.Storage.BlobCreated'` + `'Microsoft.Storage.BlobDeleted'` | Verified (positive presence only — see DR-A) |
| Actionable messages | lines 233-238 ("…must reference blobEventsQueueName ('blob-events')… not a raw 'doc-processing' queue…"), 249-255 ("…Both BlobCreated and BlobDeleted must fan out to blob-events…") | Verified |
| No `Pillar:` header on the function | Function has only a docstring; file-level Pillar header at line 1 | Verified |
| Test passes | Ran `python -m pytest tests/infra/test_main_bicep.py -q` → **35 passed in 0.04s** (matches changes-log "35 passed") | Verified |
| Bicep target exists | `v2/infra/main.bicep`: `var blobEventsQueueName = 'blob-events'` line 2152; new-topic sub `queueName: blobEventsQueueName` line 2421 + `includedEventTypes` line 2426; existing-topic sub `queueName: blobEventsQueueName` line 2487 + `includedEventTypes` line 2492 | Verified |
| Mutation makes test fail | **Empirically false for a single-subscription mutation** — see DR-A | Deviation |

## Findings by severity

### Major

#### DR-A — Regression guard does not satisfy the "either subscription regresses" success criterion

The plan's Success Criteria states the guard must fail *"if **either** Event Grid subscription's `queueName` regresses from `blob-events`"* (plan Success Criteria, first bullet). The committed `v2/infra/main.bicep` contains **two** subscription resources that both carry the destination:

* new-topic `blobCreatedSubscription` — `queueName: blobEventsQueueName` at line 2421 (gated `if (!useExistingEventGridTopic)`);
* existing-topic `existingEventGridSubscription` — `queueName: blobEventsQueueName` at line 2487 (gated `if (useExistingEventGridTopic)`).

The test asserts only **substring membership** against the whole-file text:

```python
assert "queueName: blobEventsQueueName" in bicep_text   # line 233
```

Because the literal appears twice, an `in` check passes if **at least one** occurrence remains. Read-only in-memory simulation (no file committed) confirmed:

* `queueName: blobEventsQueueName` occurrences: **2**
* pin still present after mutating **one** subscription to `docProcessingQueueName`: **True** → test still passes
* pin present after mutating **both**: **False** → test fails
* `'Microsoft.Storage.BlobCreated'` occurrences: **2**; still present after dropping it from one subscription: **True** → test still passes

Consequence: the precise BUG-0054 regression — repointing the **new-topic** `blobCreatedSubscription` (the common new-storage deploy path) back to `doc-processing` while the existing-topic reuse block keeps the pin — would **not** be caught. The details' own verification clause ("Mutating the bicep subscription `queueName` to `docProcessingQueueName` makes the new test fail") holds only if **all** occurrences are mutated; the "verify mentally" instruction (details Step 1.1) missed the two-occurrence reality. The guard catches a *total* regression (both subs repointed, or the var removed/renamed) but not a *single-path* one.

Remediation options (not applied — validation is read-only): slice the bicep text per subscription resource and assert per-slice, or add a count assertion (`bicep_text.count("queueName: blobEventsQueueName") == 2` with a matching `docProcessingQueueName`-absence check scoped to the subscription blocks).

### Minor

#### DR-B — Changes-log "closes the BUG-0054 regression-guard gap" overstates coverage

The changes-log Modified entry states the test *"closes the BUG-0054 regression-guard gap (DR-01)"* and the Release Summary says it *"fails if either Event Grid subscription regresses off the `blob-events` queue."* Given DR-A, this is an overstatement: the guard closes the *total*-regression vector but leaves the single-subscription regression (the exact original BUG-0054 shape) uncaught. The claim should be scoped to "adds a total-regression guard."

#### DR-C — No negative / scoped assertion for `doc-processing`

The details frame the test as asserting the destination *"never regresses to `doc-processing`"* (details Step 1.1). The implemented test contains only **positive** presence assertions; there is no negative assertion (e.g. `"queueName: docProcessingQueueName" not in <subscription slice>`). A scoped negative assertion is what would have closed DR-A; its absence is why the partial regression slips through.

### Info

#### DR-D — `subjectBeginsWith` left unguarded (consistent with narrowed plan scope)

Research §5 (infra-wiring.md line 145) identified the gap as *"no test asserting the … `queueName` is `blob-events` … nor asserting `includedEventTypes` / `subjectBeginsWith`."* The details deliberately scoped Step 1.1 to `queueName` + the two event types only (no `subjectBeginsWith`), so the implementation matches the plan — but the research-identified gap is only **partially** closed. Not a defect against the plan; noted for completeness.

#### DR-E — `uv run pytest` trampoline fallback (DE-01) accurately recorded

The changes-log "Additional or Deviating Changes" and planning-log DE-01 record that `uv run pytest` failed locally with "failed to canonicalize script path" and validation fell back to `.venv\Scripts\python.exe -m pytest`. This validation reproduced the green result via the same `.venv` interpreter (35 passed). Environment-only; no code impact. Accurately documented.

## Coverage assessment

* **Plan items implemented:** Step 1.1 is the sole step of Phase 1. The test exists, runs, passes (35/35), uses the correct fixture, covers both event types, carries actionable sibling-voice messages, and correctly omits a per-function `Pillar:` header. **7 of 8 sub-requirements Verified.**
* **Gap:** the 8th sub-requirement (the plan-level "fails if **either** subscription regresses" success criterion, and the details' "mutating … makes the test fail" verification) is **not met** for a single-subscription regression — the precise BUG-0054 vector. This is the one Major.
* **Changes-log accuracy:** structurally accurate (file, test name, assertions, "35 passed" all confirmed); two coverage claims (DR-B) are overstated relative to the implemented guard.
* **No missing files, no unlisted changes for Phase 1.** The Phase 1 footprint is exactly one modified file (`v2/tests/infra/test_main_bicep.py`), matching the changes-log.

## Severity tally

| Severity | Count | IDs |
| --- | --- | --- |
| Critical | 0 | — |
| Major | 1 | DR-A |
| Minor | 2 | DR-B, DR-C |
| Info | 2 | DR-D, DR-E |

## Recommended next validations (not performed this session)

- [ ] Phase 2 — `parser_key_for_path` extraction + four call-site repoints (`v2/src/backend/core/paths.py`, `test_paths.py`, batch_push/add_url blueprints, `services/ingestion.py`).
- [ ] Phase 3 — `resolve_search_provider` / `ResolvedSearch` extraction + three blueprint `_execute` repoints (`v2/src/functions/core/search_resolution.py`).
- [ ] Phase 4 Step 4.1 — `v2/docs/bugs.md` BUG-0054 reconciliation (detail block L973-991 + summary row L113); confirm placeholder discipline (Hard Rule #18).
- [ ] Phase 5 — full-sweep + pyright gate claims (`2514 passed, 1 skipped`; `0 errors / 0 warnings / 0 information`).

## Clarifying questions

1. Is the single-subscription blind spot (DR-A) acceptable as-is, given the two subscription resources are mutually exclusive at deploy time (`if (useExistingEventGridTopic)`), or should the guard be tightened to a per-subscription / count + negative-`doc-processing` assertion so the common new-storage path can't silently regress? (Tightening is a one-line-class change to the existing test, no structural impact.)
