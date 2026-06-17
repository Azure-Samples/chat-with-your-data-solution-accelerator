---
title: CWYD v2 — Remaining Work Summary
description: Snapshot of recently completed demo-polish work and the remaining open issues for CWYD v2, grouped by area and severity.
author: CWYD Engineering
ms.date: 2026-06-15
ms.topic: status
keywords:
  - status
  - remaining work
  - open issues
  - v2
estimated_reading_time: 4
---

## Overview

The v2 MVP is functionally complete: every phase in [development_plan.md](development_plan.md) (Phases 1–8) is done and green. What remains is a short bug backlog plus a couple of operational items. Observed defects are tracked in [bugs.md](bugs.md); day-to-day notes live under [worklog/](worklog/).

## Recently completed

* **BUG-0040 → BUG-0042** — citation / reference panel polish.
* **BUG-0044** — stale conversation-route test.
* **BUG-0046** — frontend user identity + per-user chat-history isolation. Fully fixed and live-verified, including the `HistoryPanel` fifth-seam catch (its inline `fetch` was missing the `x-ms-client-principal-id` header).
* **BUG-0045** — chat-page double scroll. Fix landed by the author; the registry entry in [bugs.md](bugs.md) still needs flipping from `open` to `fixed`.

## Open issues

All currently open entries, grouped by area. Severity and status are summarized in the table, with detail below.

| ID       | Area      | Severity | Status                              | Summary                                                          |
|----------|-----------|----------|-------------------------------------|-----------------------------------------------------------------|
| BUG-0034 | functions | high     | open                                | Uploaded document reports success but never gets indexed/listed |
| BUG-0029 | backend   | medium   | open (latent)                       | `max_tokens` vs `max_completion_tokens` for gpt-5 / o-series    |
| BUG-0032 | backend   | low      | open                                | Admin prompt-override round-trip can double-wrap the guardrail  |
| BUG-0043 | backend   | low      | open                                | Raw KB citation markers leak into the reasoning panel           |
| BUG-0045 | frontend  | medium   | fix landed — registry flip pending  | Chat-page double scroll                                         |

### Functions

* **BUG-0034 (high)** — An operator uploads a document through the admin Add-data UI; the request returns `200` with an `UploadResponse` (the UI shows success), but the document never appears in the documents list and is never indexed. Likely an environment gap (no Functions host draining the doc-processing queue locally) rather than a code defect. Diagnosis path: confirm the blob landed, confirm a queue message was enqueued, confirm a Functions host consumed it, confirm the Search push ran. **Highest-priority open item.**

### Backend

* **BUG-0029 (medium, latent)** — `FoundryIQ.chat()` sends OpenAI Chat Completions `max_tokens`, which gpt-5 / o-series reject (`400`, "Use 'max_completion_tokens' instead"). Latent because the `langgraph` chat path does not thread `max_tokens`, so it is not currently triggered.
* **BUG-0032 (low)** — The admin prompt-override round-trip can double-wrap the guardrail: `GET /api/admin/config` returns the already-wrapped default, and if the editor pre-populates and re-saves, `resolve_cwyd_instructions` wraps it again so `CWYD_GUARDRAIL` appears twice.
* **BUG-0043 (low)** — Raw native Foundry IQ KB citation markers (`【N:M†source】`) leak into the reasoning panel on the `agent_framework` path, because `normalize_kb_citations` runs only over the answer string, not the `text_reasoning` blocks forwarded to the `reasoning` channel. Planned fix: a `strip_kb_markers()` helper in `tools/citations.py` applied to reasoning text. Quick win.

### Frontend

* **BUG-0045 (medium)** — Chat-page double scroll. The fix has landed; the [bugs.md](bugs.md) registry entry still shows `open` and needs flipping to `fixed`, ideally with a regression note so it cannot silently return.

## Operational / non-blocking

* **`azd deploy`** (code-only, to the existing environment) is pending an explicit go-ahead.
* **4 pre-existing eslint errors** in `CitationPanel.tsx` / `MessageList.tsx` (`no-confusing-void-expression`, `prefer-nullish-coalescing`) — a small cleanup unit, surfaced only by whole-tree lint.
* **9 advisory `react-refresh` lint warnings** — non-blocking HMR hints.
* **Phase 8 deferred parser shelf** (Markdown/HTML, JSON, images) — explicitly out of scope.

## Suggested next steps

1. Diagnose **BUG-0034** — the ingestion gap is the only high-severity open item; start the Functions host locally and trace an upload through the queue.
2. Fix **BUG-0043** — a genuine quick win with a ready plan (the reasoning-panel marker strip).
3. Flip **BUG-0045** to `fixed` in the registry and add a regression note.
