<!-- markdownlint-disable-file -->
# Subagent Research: BUG-0054 ingestion-trigger code path — duplication & bad-implementation audit

Status: Complete

Scope: Read-only analysis of the blob-event / ingestion-trigger code path for BUG-0054, to surface duplicated
logic and bad implementation a fix should consolidate. No production code modified.

Headline finding (read first): the `blob_event` trigger code path is **already well-built** and satisfies the
Hard Rules the task hypothesized it might violate (#4 registry dispatch, #11 StrEnum, #14 SDK boundary, #15 typed
dict returns, #17 imports-at-top). The `doc-processing` envelope is a **single typed model** (`BatchPushQueueMessage`)
written through a **single writer** (`enqueue_push_message`) — there is **no** copy-pasted field assembly and **no**
hand-rolled Event Grid parsing. BUG-0054's open remainder is a **deployment/cloud-cutover** problem, not a
bad-implementation-in-the-trigger problem. The genuine consolidation opportunities are three repeated *wiring*
blocks (search-provider resolution, `_build_document`, extension-key derivation), described in §5.

---

## 1. `blob_event/` module structure

Folder: `v2/src/functions/blob_event/` — `blueprint.py`, `event_parser.py`, `handler.py`, `__init__.py`.

### 1a. `blueprint.py` — queue trigger + dispatch

- Imports all at module top (Hard Rule #17 clean): v2/src/functions/blob_event/blueprint.py lines 49-65.
- Fixed infra constant for the queue name (not a `%APP_SETTING%` env-ref, by design — see docstring): `_BLOB_EVENTS_QUEUE = "blob-events"` at v2/src/functions/blob_event/blueprint.py line 70.
- The trigger itself is thin: v2/src/functions/blob_event/blueprint.py lines 153-169.

  ```python
  @bp.queue_trigger(
      arg_name="msg",
      queue_name=_BLOB_EVENTS_QUEUE,
      connection="AzureWebJobsStorage",
  )
  @log_queue_errors("blob_event")
  async def blob_event(msg: func.QueueMessage) -> None:
      await _execute(msg, get_settings())
  ```

- The `_execute` seam (v2/src/functions/blob_event/blueprint.py lines 73-151) does:
  1. `parse_blob_event(msg.get_body())` → typed `ParsedBlobEvent | None`; `None` ⇒ skip before any SDK client opens (line 92-94).
  2. Resolve the credentials provider **registry-first** (Hard Rule #4): v2/src/functions/blob_event/blueprint.py lines 95-97.
  3. **Branch on `event.event_type`** (a `BlobEventType` StrEnum), not a string:
     - `CREATED` ⇒ open the `doc-processing` `QueueClient` and call `handle_blob_created` (lines 98-108).
     - `DELETED` ⇒ resolve the registry-first search provider (pgvector pool only on the pgvector path) and call `handle_blob_deleted` (lines 109-151).

  Quote — the classify-and-dispatch core (v2/src/functions/blob_event/blueprint.py lines 92-108):

  ```python
  event = parse_blob_event(msg.get_body())
  if event is None:
      return None
  cred_provider = credentials_registry.registry.get(
      credentials_registry.select_default(settings.identity.uami_client_id)
  )(settings=settings)
  async with await cred_provider.get_credential() as credential:
      if event.event_type is BlobEventType.CREATED:
          _blob_endpoint, queue_endpoint = resolve_storage_endpoints(settings.storage)
          async with QueueClient(
              account_url=queue_endpoint,
              queue_name=settings.storage.doc_processing_queue,
              credential=credential,
          ) as queue_client:
              return await handle_blob_created(event.ref, queue_client)
  ```

### 1b. `event_parser.py` — Event Grid envelope → typed model (CLEAN, NO duplication)

- `BlobEventType(StrEnum)` with `CREATED = "Microsoft.Storage.BlobCreated"` / `DELETED = "Microsoft.Storage.BlobDeleted"`: v2/src/functions/blob_event/event_parser.py lines 45-55. **Satisfies Hard Rule #11** (closed-set event types are a StrEnum, not bare strings).
- Reverse map for narrowing a raw `eventType` without try/except: v2/src/functions/blob_event/event_parser.py line 60.
- Two frozen `extra="forbid"` Pydantic models: `ParsedBlobRef` (container + filename) at lines 63-76, `ParsedBlobEvent` (event_type + ref) at lines 79-92. **Satisfies Hard Rule #15** (closed-set parse result is a typed model, not `dict[str, Any]`).
- `subject`-regex extraction (`/blobServices/default/containers/<c>/blobs/<b>`): `_BLOB_SUBJECT_RE` at lines 36-41, `parse_blob_created_subject` at lines 95-114. One subject parser serves **both** create and delete (same subject shape) — explicitly noted in the `parse_blob_event` docstring (lines 152-160).
- `_decode_event_payload` (lines 117-141) tolerates raw-JSON **or** base64 bodies defensively (Event Grid wire encoding is an external behavior), unwraps a single-event JSON array, returns `None` for non-object bodies. The `cast("dict[str, Any]", payload)` at line 141 is a justified Hard Rule #11(a) SDK-boundary carve-out (the decoded Event Grid blob is an externally-owned shape).
- `parse_blob_event` (lines 144-172) is the public entry: malformed/non-JSON body, unknown `eventType`, or non-blob `subject` all yield `None` ⇒ caller skips. Quote (lines 161-172):

  ```python
  payload = _decode_event_payload(raw)
  if payload is None:
      return None
  event_type_raw = payload.get("eventType")
  event_type = (
      _EVENT_TYPE_BY_VALUE.get(event_type_raw)
      if isinstance(event_type_raw, str) else None
  )
  if event_type is None:
      return None
  subject = payload.get("subject")
  if not isinstance(subject, str):
      return None
  ref = parse_blob_created_subject(subject)
  if ref is None:
      return None
  return ParsedBlobEvent(event_type=event_type, ref=ref)
  ```

- **Confirmed via grep**: `BlobCreated|BlobDeleted|eventType|EventGrid|event_grid|subject` matches **only** `blob_event/event_parser.py` + `blob_event/blueprint.py` + `blob_event/handler.py` in `v2/src/` (plus a minified frontend bundle false-positive). There is **no second Event Grid parser** anywhere in the backend or functions tier. The task's hypothesis of "Event Grid envelope parsing duplicated or hand-rolled" is **not present**.

### 1c. `handler.py` — two pure actions (create ⇒ enqueue, delete ⇒ de-index)

- `BlobEventOutcome` discriminated record (frozen, `extra="forbid"`): v2/src/functions/blob_event/handler.py lines 41-58.
- `handle_blob_created` (lines 61-87): builds a `BatchPushQueueMessage(container_name=ref.container_name, filename=ref.filename, force_reindex=False)` (lines 71-75) and calls `enqueue_push_message(queue_client, message)` (line 76). Adds **no** try/except — the writer owns the AzureError boundary (Hard Rule #14 delegation, documented in the docstring lines 68-70).
- `handle_blob_deleted` (lines 90-110): calls `search.delete_by_source(ref.filename)` (line 102) — same source key `batch_push` indexes on, so create+delete round-trip. DI'd `search` owns its SDK boundary.

---

## 2. `batch_push/` — the unchanged `doc-processing` consumer

- `blueprint.py` queue trigger binds `queue_name="%AZURE_DOC_PROCESSING_QUEUE%"` (host env-ref expansion) with `connection="AzureWebJobsStorage"`: v2/src/functions/batch_push/blueprint.py lines 151-165.
- It expects a `BatchPushQueueMessage` envelope. `queue_reader.parse_push_message` (v2/src/functions/batch_push/queue_reader.py lines 27-36) is the parse step: `BatchPushQueueMessage.model_validate_json(msg.get_body())` — accepts `bytes` directly, no intermediate decode. A drifted/malformed body raises `pydantic.ValidationError` ⇒ propagates ⇒ runtime retry → poison (the BUG-0054 symptom: a raw Event Grid `BlobCreated` envelope fails this validation, which is exactly why the `blob_event` translator exists so Event Grid events never reach `doc-processing` un-translated).
- `_execute` (v2/src/functions/batch_push/blueprint.py lines 91-150) resolves credentials, parser, embedder, and search provider via the registries, then runs `batch_push_handler` (download → parse → embed → push). **It does not enqueue** — it is the consumer; the only "message shaping" is the inbound `model_validate_json`.

---

## 3. `add_url/` — URL ingestion path

- `add_url` is **HTTP-triggered** (`POST /api/add_url`), not queue-based, and does **not** build a `doc-processing` message at all. It fetches the URL inline and writes chunks straight to the search index (fetch → parse → embed → push), bypassing the queue entirely: v2/src/functions/add_url/blueprint.py lines 144-176 (trigger) and v2/src/functions/add_url/handler.py lines 116-167 (`add_url_handler`).
- So **no `doc-processing` envelope is constructed in `add_url`** — refutes the hypothesis that `add_url` is a fourth copy of the envelope assembly. (The backend `ingest_url` admin path *does* write a blob + enqueue, but it goes through `upload_document` → the single shared writer; see §4.)

---

## 4. Backend ingestion service + the single envelope writer (NO cross-tier duplication)

- `v2/src/backend/services/ingestion.py` **imports and reuses** the Functions-tier writer and model rather than redefining them:
  - `from functions.batch_start.queue_writer import enqueue_push_message` — v2/src/backend/services/ingestion.py line 52.
  - `from functions.core.contracts import BatchPushQueueMessage` — v2/src/backend/services/ingestion.py line 53.
- `upload_document` (lines ~250-330) writes the blob, then — **only when `settings.storage.ingestion_trigger is IngestionTrigger.DIRECT_ENQUEUE`** — builds the envelope and enqueues. Quote (v2/src/backend/services/ingestion.py lines 320-332):

  ```python
  if backend_enqueues:
      message = BatchPushQueueMessage(
          container_name=container_name,
          filename=filename,
          ingestion_job_id=ingestion_job_id,
      )
      await enqueue_push_message(queue_client, message)
  ```

- Under `IngestionTrigger.EVENT_GRID` the backend writes the blob only and returns `queued=False`, letting Event Grid → `blob-events` → `blob_event` drive ingestion (avoids double-ingest). This is the ADR 0028 single-trigger cutover lever.

### The envelope model

- **One model, one source of truth**: `BatchPushQueueMessage` (frozen, `extra="forbid"`, `str_strip_whitespace=True`) — v2/src/functions/core/contracts.py lines 27-62. Fields: `container_name`, `filename`, `ingestion_job_id` (uuid4 default factory), `force_reindex` (default `False`). The module docstring (lines 1-22) explicitly states it is the *single* cross-blueprint wire contract.
- **One writer**: `enqueue_push_message` — v2/src/functions/batch_start/queue_writer.py lines 33-66. It is the **only** place `queue_client.send_message(...)` is called for `doc-processing`, and it wraps `AzureError` with structured `logger.exception` extras then re-raises (Hard Rule #14 compliant — lines 55-66).
- **Construction sites (3, all using the one model + one writer)**:
  1. `functions/batch_start/handler.py` line 61 — bulk fan-out (one envelope per listed blob, shared `ingestion_job_id`, `force_reindex=request.force_reindex`).
  2. `functions/blob_event/handler.py` line 71 — Event Grid create (`force_reindex=False`, fresh `ingestion_job_id` via default factory).
  3. `backend/services/ingestion.py` line 326 — admin DIRECT_ENQUEUE upload (explicit `ingestion_job_id`).
  These are three small constructor calls that pass **different** field sets (force_reindex / ingestion_job_id semantics differ per path); they are **not** copy-pasted field assembly of a dict and they do **not** re-implement the wire format. This is the correct shared-builder pattern, not a smell.

---

## 5. Duplication & bad-implementation audit (the actionable findings)

### Hard-Rule checks — ALL PASS in the ingestion-trigger path

| Hypothesized smell | Verdict | Evidence |
| --- | --- | --- |
| Duplicated `doc-processing` envelope construction | **Not present** | Single typed `BatchPushQueueMessage` (contracts.py:27) + single `enqueue_push_message` writer (queue_writer.py:33). 3 construction sites all reuse them. |
| Hand-rolled / duplicated Event Grid parsing | **Not present** | Only `blob_event/event_parser.py`; typed `ParsedBlobEvent`/`ParsedBlobRef` models + `BlobEventType` StrEnum. grep confirms no second parser. |
| `if/elif` provider dispatch (should be registry, #4) | **Not present** | Providers resolved via `*_registry.registry.get(key)(...)` everywhere (credentials, parsers, embedders, search). The lone `if search_key == IndexStore.PGVECTOR:` branch is a **kwarg injection** (inject the asyncpg `pool`), not a provider selection — the provider is still registry-resolved. Compliant. |
| Bare-string closed sets (should be StrEnum, #11) | **Not present** | `BlobEventType`, `IngestionTrigger`, `IndexStore`, `OrchestratorName` are all `StrEnum` (event_parser.py:45, settings.py:108/`IngestionTrigger`). No bare-string event-type/mode comparisons. |
| Missing SDK boundary try/except (#14) | **Not present** | `enqueue_push_message` wraps `AzureError`; `upload_blob` wrapped in ingestion.py:307-317; queue/search SDK clients in `blob_event._execute` delegate the actual send/delete to wrapped helpers, and `@log_queue_errors("blob_event")` is the trigger-level re-raise boundary. |
| In-function imports (#17) | **Not present** | All imports at module top in every file read (blueprint.py:49-65, event_parser.py:27-33, handler.py:34-37, ingestion.py:39-56). |

### REAL consolidation opportunities (wiring duplication, not contract duplication)

These are the honest "duplicated logic" sites a refactor could consolidate. None of them is a BUG-0054
correctness defect — they are DRY/maintenance smells in the *collaborator-wiring* boilerplate.

1. **Search-provider resolution + pgvector-pool wiring + `ensure_schema` + `aclose` block — duplicated 4×.**
   The identical ~25-30 line skeleton (`search_kwargs = {settings, credential}` → `if PGVECTOR: pool = await PgVectorPool(...).acquire()` → `search_registry.registry.get(search_key)(**search_kwargs)` → `ensure_schema()` → `try/finally aclose`), including the **same** repeated `Any`-carve-out comment, appears in:
   - v2/src/functions/batch_push/blueprint.py lines 123-150
   - v2/src/functions/add_url/blueprint.py lines 113-141
   - v2/src/functions/blob_event/blueprint.py lines 109-145
   - v2/src/backend/app.py lines 158-184 (lifespan variant — uses `database_client.ensure_pool()` instead of a fresh `PgVectorPool`, but the same shape)
   **Smell**: largest copy-paste in the path; each new ingestion trigger re-pastes it (the `blob_event` blueprint is itself a paste of `batch_push`'s `_execute`). **Suggested consolidation**: an async context-manager helper under `functions/core/` (e.g. `resolve_search_provider(settings, credential) -> AsyncIterator[BaseSearch]`) that owns the pgvector-pool branch + `ensure_schema` + `aclose`, so all four call sites become `async with resolve_search_provider(...) as search:`. Keep the backend lifespan variant's pool-source difference (`database_client.ensure_pool()` vs a per-call `PgVectorPool`) as a parameter. This is a structural change → triggers **Hard Rule #10 (ask the user first)** before extracting.

2. **`_build_document(chunk, vector) -> SearchDocument` — duplicated 2×.**
   - v2/src/functions/batch_push/handler.py line 57
   - v2/src/functions/add_url/handler.py line 90
   The `add_url` copy is **explicitly documented as intentional** duplication (handler.py lines 38-43: "Per-blueprint independence is a Stable Core invariant — the two ingestion paths must be free to evolve their search-document shapes independently"). **Smell**: low — this is a deliberate design choice, not an accident. **Suggested action**: leave as-is unless a fix genuinely needs a shared mapping; if consolidated, it must be justified against the documented independence rationale.

3. **Extension / parser-key derivation `PurePosixPath(...).suffix.lstrip(".").lower()` — duplicated 4×.**
   - v2/src/functions/batch_push/blueprint.py line 90 (`_parser_key_for_filename`)
   - v2/src/functions/add_url/blueprint.py line 92 (`_parser_key_for_url`, with URL-path + ext-less fallback)
   - v2/src/backend/services/ingestion.py line 94 (`_blob_name_for_url`)
   - v2/src/backend/services/ingestion.py line 217 (`validate_upload`)
   **Smell**: low-medium — the same one-liner extension extraction is re-authored four times; the two blueprint helpers (`_parser_key_for_filename` / `_parser_key_for_url`) are near-identical and even cross-reference each other in docstrings. **Suggested consolidation**: a single `parser_key_for_path(path_or_url, *, default=None)` helper under `functions/core/` (or `backend.core`) that both blueprints + the backend service call. Structural → Hard Rule #10.

### Why this matters for a BUG-0054 fix specifically

- BUG-0054's *code* (the `blob_event` translator + bicep repoint) is **done and locally validated** (bugs.md lines ~973-1010). The **open** remainder is **cloud-only**: deploy `blob_event` to the cloud Function App (the `azd deploy function` Flex remote-build hang), then flip `AZURE_ENV_INGESTION_TRIGGER=event_grid` + `azd provision` to remove the backend double-enqueue, and re-validate end-to-end. The `alwaysReady` instance for `function:blob_event` already landed in `infra/main.bicep` (2026-06-29, guarded by `test_function_app_keeps_blob_event_always_ready`).
- Therefore a BUG-0054 "fix that consolidates duplicated logic / bad implementation" has **no required code-consolidation target in the trigger path** — the trigger code is clean. If the intent is to reduce debt *while* closing BUG-0054, finding #1 (the 4× search-provider-resolution block) is the highest-value, but it is **scope-separate** from BUG-0054's deployment remainder and is a Hard Rule #10 structural change requiring user sign-off.

---

## References (file:line)

- v2/src/functions/blob_event/blueprint.py — trigger + `_execute` dispatch (lines 70, 73-151, 153-169)
- v2/src/functions/blob_event/event_parser.py — `BlobEventType` StrEnum (45-55), typed parse models (63-92), `_decode_event_payload` (117-141), `parse_blob_event` (144-172)
- v2/src/functions/blob_event/handler.py — `handle_blob_created` (61-87), `handle_blob_deleted` (90-110)
- v2/src/functions/batch_push/blueprint.py — trigger (151-165), `_execute` search-resolution block (123-150), `_parser_key_for_filename` (82-90)
- v2/src/functions/batch_push/queue_reader.py — `parse_push_message` (27-36)
- v2/src/functions/batch_push/handler.py — `_build_document` (57)
- v2/src/functions/add_url/blueprint.py — HTTP trigger (144-176), `_execute` search-resolution block (113-141), `_parser_key_for_url` (75-93)
- v2/src/functions/add_url/handler.py — `add_url_handler` (116-167), `_build_document` (90), intentional-duplication note (38-43)
- v2/src/functions/batch_start/handler.py — fan-out envelope construction (61)
- v2/src/functions/batch_start/queue_writer.py — `enqueue_push_message` single writer + AzureError boundary (33-66)
- v2/src/functions/core/contracts.py — `BatchPushQueueMessage` single envelope model (27-62)
- v2/src/functions/core/storage_endpoints.py — `resolve_storage_endpoints` shared `.blob.→.queue.` helper (24-58)
- v2/src/backend/services/ingestion.py — reuses functions writer+model (52-53), `upload_document` DIRECT_ENQUEUE construction (320-332), extension derivation (94, 217)
- v2/src/backend/core/settings.py — `IngestionTrigger` StrEnum (`DIRECT_ENQUEUE`/`EVENT_GRID`)
- v2/src/backend/app.py — lifespan search-resolution block (158-184)
- v2/docs/bugs.md — BUG-0054 entry (973-1010)
- v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md — single-trigger design, B1 queue-translator decision

---

## Recommended next research (not done this session)

- [ ] Read the existing BUG-0054 fix artifacts already in-tree to avoid re-planning a done task: `.copilot-tracking/research/2026-06-29/bug-0054-fix-research.md`, `.copilot-tracking/plans/2026-06-29/bug-0054-fix-plan.instructions.md`, `.copilot-tracking/details/2026-06-29/bug-0054-fix-details.md` (the fix appears to already be scoped to always-ready + stale-doc reconciliation, NOT code consolidation).
- [ ] If finding #1 (4× search-provider-resolution consolidation) is in scope, read `v2/src/functions/core/pgvector_pool.py` and `v2/src/backend/core/providers/search/base.py` to design the shared `resolve_search_provider` context manager and confirm the AzureSearch/pgvector `aclose` + `ensure_schema` contracts match across all four call sites.
- [ ] Confirm the test surface that would need updating if any consolidation lands: `v2/tests/functions/blob_event/**`, `v2/tests/functions/batch_push/**`, `v2/tests/functions/add_url/**` (the `_execute` monkeypatch seams).

## Clarifying questions

1. **Is BUG-0054's remaining work a code change at all?** The bug's open remainder is a cloud deploy + env-flip + re-validate; the trigger code is done and locally validated. Does this task want (a) to close the *deployment* remainder, or (b) a debt-reduction refactor of the ingestion wiring that happens to touch the BUG-0054 path? They are different units.
2. **If consolidation is wanted**, which of the three findings is in scope? Finding #1 (search-provider resolution, 4×) is the highest value but is a Hard Rule #10 structural change (new shared helper under `functions/core/`) requiring user sign-off before any code lands. Finding #2 (`_build_document`) is documented-intentional duplication and would need an explicit override of that rationale.
