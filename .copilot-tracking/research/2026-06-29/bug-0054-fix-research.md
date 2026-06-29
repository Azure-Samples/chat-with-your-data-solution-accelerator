<!-- markdownlint-disable-file -->
# Research: BUG-0054 in-repo fix — blob_event always-ready + stale-doc reconciliation

## Scope

BUG-0054 (`v2/docs/bugs.md`, Area: infra, Severity: medium, Status: open) — a stray
Event Grid subscription delivered raw `Microsoft.Storage.BlobCreated` envelopes into the
`doc-processing` queue, where `batch_push` validates a strict CWYD `BatchPushQueueMessage`,
so every event failed validation and poisoned (`doc-processing-poison`, 10 envelopes).

The fix (ADR 0028, option B1) is **already implemented and locally proven (2026-06-20)**:
a `blob_event` queue-trigger blueprint translates the raw event into a CWYD envelope behind
a dedicated `blob-events` queue; the Event Grid subscription is repointed onto `blob-events`;
a `StorageSettings.ingestion_trigger` (`direct_enqueue` | `event_grid`) flag lets the backend
stop double-enqueuing once Event Grid owns ingestion.

This research scopes the **in-repo** remainder (the cloud cutover is operational and deferred).

## Verified findings (review of code + infra + docs, 2026-06-29)

### Implementation is complete and internally consistent

- `v2/src/functions/blob_event/{blueprint,handler,event_parser}.py` — typed, registry-first,
  follow Hard Rules #4/#11/#14/#15; registered in `v2/src/functions/function_app.py`.
- `IngestionTrigger` StrEnum + `StorageSettings.ingestion_trigger`
  (`v2/src/backend/core/settings.py`) — correct (hard enum, no `str` arm; env
  `AZURE_INGESTION_TRIGGER`).
- `backend/services/ingestion.py::upload_document` branches on
  `backend_enqueues = settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE`;
  under `event_grid` it writes the blob only and returns `queued=False`.
- Infra (`v2/infra/main.bicep`): `blob-events` + `blob-events-poison` queues exist (new- and
  existing-storage paths); Event Grid subscription repointed to `blob-events` with both
  `BlobCreated` + `BlobDeleted` filters; role-before-subscription ordering fixed (BUG-0061);
  param `ingestionTrigger` → `AZURE_ENV_INGESTION_TRIGGER` (default `direct_enqueue`) → backend
  container env `AZURE_INGESTION_TRIGGER`. Names match end-to-end.
- `v2/src/functions/host.json` carries `extensions.queues.messageEncoding = "none"` — the
  BUG-0056 durable back-port **has landed**.

### Gap 1 (real, mergeable) — `blob_event` missing from Flex `alwaysReady`

`v2/infra/main.bicep` `functionAppConfig.scaleAndConcurrency.alwaysReady` (≈ lines 2229-2234)
lists only:

```bicep
alwaysReady: [
  {
    name: 'function:batch_push'
    instanceCount: 1
  }
]
```

`blob_event` is also a queue trigger (on `blob-events`), so in Flex Consumption it carries the
same scale-from-zero failure BUG-0053 documented and fixed for `batch_push`. The BUG-0054
"To resume" note explicitly calls for "add an `alwaysReady` instance for `function:blob_event`
per BUG-0053." BUG-0053 itself is **fixed** — only `batch_push` got the always-ready entry.

Infra is guarded by `v2/tests/infra/test_main_bicep.py` (grep-style text assertions over
`main.bicep`; module fixture `bicep_text`, plus a `function_app_slice` fixture). No
`alwaysReady` assertion exists yet → a test-first guard can land alongside the bicep edit.

### Gap 2 (stale docs)

- ADR `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md`, `## Follow-ups`, first
  bullet: "The live `AzureFunctionsJobHost__extensions__queues__messageEncoding = none` is
  still not in `host.json` / bicep." — STALE; `host.json` has it.
- `v2/docs/bugs.md` BUG-0056 entry (≈ line 1019): "Durable back-port: add the same host setting
  to `host.json` ... (follow-up; bicep edits paused)." — STALE; `host.json` has it.
- `v2/docs/bugs.md` BUG-0054 "To resume" (≈ line 987): once the `alwaysReady` entry lands, that
  step is done and the note should reflect only the remaining cloud deploy + flag flip.

### Gap 3 (minor, latent — decision needed)

ADR 0028 Consequences (−): "`UploadResponse` ... its `ingestion_job_id` no longer correlates to
the real ingest job ... The field is dropped or marked informational." Current code under
`event_grid` still mints a fresh `uuid4` `ingestion_job_id` and returns it with `queued=False`
— neither dropped nor marked. Non-breaking (the FE polls `GET /api/admin/documents`); only
matters once `event_grid` is the live trigger (gated on cloud cutover). Candidate to defer.

### Dependency-order finding

Full cloud closure of BUG-0054 (a successful `azd deploy function` that ships `blob_event`,
then `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision`) depends on
**BUG-0058** (prepackage / stale-artifact — #3 in the numerical fix queue, code-fixed but not
cloud-verified) plus resolving the Flex remote-build timeout that parked the deploy. BUG-0053
(the other gate) is **fixed**. So the cloud cutover sequences **after** BUG-0058 despite
BUG-0054 being #1 numerically. The cloud cutover is therefore out of scope for this in-repo plan.

## Constraints

- Hard Rule #2 (test-first): the bicep edit lands with a `test_main_bicep.py` guard.
- Hard Rule #10 (structure): adding an entry to an existing array is a content edit, not a
  structural change — no user confirmation gate.
- Hard Rule #12 / #19: BUG-0054 "To resume" is a defect-registry edit in `bugs.md`; ADR is a doc.
- `dont-restructure-working-code`: dropping `ingestion_job_id` would touch the `UploadResponse`
  wire model + FE + tests for a latent path — over-engineering; prefer defer.

## Selected approach

1. Add `{ name: 'function:blob_event', instanceCount: 1 }` to the bicep `alwaysReady` array,
   guarded by a new `test_main_bicep.py` grep test (test-first).
2. Reconcile the three stale doc notes (ADR 0028 Follow-ups, bugs.md BUG-0056, bugs.md BUG-0054
   "To resume").
3. Defer Gap 3 (dead `ingestion_job_id`) and the cloud cutover as follow-on, tied to BUG-0058.

## References

- `v2/docs/bugs.md` — BUG-0054 (≈ 973-991), BUG-0056 (≈ 1007-1021).
- `v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md` — full ADR; `## Follow-ups`.
- `v2/infra/main.bicep` — alwaysReady (≈ 2229-2234), ingestionTrigger param (≈ 99-100), backend
  env `AZURE_INGESTION_TRIGGER` (≈ 1944), blob-events queues + Event Grid subscription.
- `v2/src/backend/services/ingestion.py` — `upload_document` (≈ 253-355).
- `v2/src/backend/core/settings.py` — `IngestionTrigger`, `StorageSettings.ingestion_trigger`.
- `v2/src/functions/host.json` — `extensions.queues.messageEncoding = "none"`.
- `v2/tests/infra/test_main_bicep.py` — grep-style infra guards (`bicep_text`,
  `function_app_slice` fixtures).
