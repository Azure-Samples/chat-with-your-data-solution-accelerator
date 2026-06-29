---
applyTo: '.copilot-tracking/changes/2026-06-29/auth-enforced-removal-transparent-identity-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: Remove `auth_enforced`, adopt transparent Easy-Auth-probe identity

## Overview

Delete the `auth_enforced` health signal and the `AuthBlocked` "Authentication Not Configured" screen so the CWYD v2 frontend resolves identity purely from Azure Easy Auth `/.auth/me` (principal → real `userId`, else the default guest user), while keeping `require_admin_auth` as the orthogonal opt-in server-side admin-write gate.

## Objectives

### User Requirements

* "We shouldn't need this variable" — remove the `auth_enforced` flag entirely. Source: 2026-06-29 conversation.
* "If the user enables identity in the frontend, that is all we need to check the login and the userId; if identity is not enabled we use the default userId, period." — identity comes from the Easy Auth probe alone. Source: 2026-06-29 conversation.

### Derived Objectives

* Delete the `AuthBlocked` component + `AuthPhase.Blocked` + `AuthState.authEnforced` — Derived from: they are the only consumers of the flag; the SPA already falls back to the default user when not enforced, so removal is deletion of a gate, not new logic (research Key Discoveries).
* Keep `require_admin_auth`, `get_user_id`, `requires_role` unchanged — Derived from: the admin-write gate is orthogonal to the UI signal (only coupling is one line in `services/health.py`); removing the signal must not weaken admin protection.
* Record the behavior change in `bugs.md` + worklog and retire the superseded design rows — Derived from: Hard Rule #0 (sync guidance) and Hard Rule #19 (durable file-based tracking).

## Context Summary

### Project Files

* v2/src/backend/models/health.py - `HealthResponse` model carrying the `auth_enforced` field to remove.
* v2/src/backend/services/health.py - `run_health_checks`, the sole producer (`auth_enforced=settings.require_admin_auth`).
* v2/src/frontend/src/App.tsx - bootstrap effect with `readAuthEnforced` + the `AuthBlocked` render branch.
* v2/src/frontend/src/hooks/useAuth.tsx - `resolve(authEnforced, userInfo)` state machine with the Blocked branch.
* v2/src/frontend/src/models/auth.tsx - `AuthPhase.Blocked` + `AuthState.authEnforced`.
* v2/src/frontend/src/components/AuthBlocked/AuthBlocked.tsx - the client-side "Authentication Not Configured" screen to delete.
* v2/src/backend/dependencies.py - `get_user_id` / `requires_role` (UNCHANGED; principal-or-default already implemented).

### References

* .copilot-tracking/research/2026-06-29/auth-enforced-removal-transparent-identity-research.md - selected approach (Scenario A), alternatives, full edit/test inventory.
* .copilot-tracking/research/subagents/2026-06-29/backend-auth-enforced-userid-research.md - backend producer/model/tests, removal decision, `require_admin_auth` retention proof.
* .copilot-tracking/research/subagents/2026-06-29/frontend-auth-enforced-identity-research.md - frontend gate inventory, default user (`DEFAULT_USER_ID`), hand-written health client (no codegen).

### Standards References

* .github/copilot-instructions.md - Hard Rule #1 (one unit/turn), #2 (test-first), #11 (StrEnum), #12 (defect-vs-debt), #16 (no process narrative in `v2/src/**`), #18 (placeholders), #19 (worklog + bugs.md).
* .github/instructions/v2-frontend.instructions.md - React/Vite frontend conventions (closed-set enums, models, identity).
* .github/instructions/v2-tests.instructions.md - test-first contract, vitest/pytest conventions.

### Execution note (CWYD)

Phases 1 and 2 touch disjoint file sets (backend vs frontend) and the SPA tolerates a missing `auth_enforced` (it narrows from an untyped payload), so they are dependency-independent. CWYD Hard Rule #1 still executes one unit per turn — each Step below is a single implement-then-test unit. Scenario C (drop ALL auth enforcement) is out of scope and recorded in the Planning Log (IP-01).

## Implementation Checklist

### [x] Implementation Phase 1: Backend — remove the `auth_enforced` health signal

<!-- parallelizable: true -->

* [x] Step 1.1: Drop `auth_enforced` from the health contract (model + producer) and update backend health tests
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 20-45)
* [x] Step 1.2: Validate backend phase changes
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 46-54)

### [x] Implementation Phase 2: Frontend — delete the gate; resolve identity from `/.auth/me`

<!-- parallelizable: true -->

* [x] Step 2.1: Collapse the `AuthState` model — drop `AuthPhase.Blocked` and `AuthState.authEnforced`
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 61-76)
* [x] Step 2.2: Make `useAuth.resolve` single-arg (`resolve(userInfo)`) and delete the Blocked branch
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 77-92)
* [x] Step 2.3: Strip the gate from `App.tsx` — remove `readAuthEnforced`, the `AuthBlocked` branch, and the `authEnforced` arg
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 93-108)
* [x] Step 2.4: Delete the `AuthBlocked` component and its test
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 109-127)
* [x] Step 2.5: Validate frontend phase changes
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 128-134)

### [x] Implementation Phase 3: Documentation & guidance sync

<!-- parallelizable: false -->

* [x] Step 3.1: Retire the `auth_enforced` design rows and log the behavior change
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 141-161)

### [x] Implementation Phase 4: Validation

<!-- parallelizable: false -->

* [x] Step 4.1: Run full project validation
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 166-173)
* [x] Step 4.2: Fix minor validation issues
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 174-177)
* [x] Step 4.3: Cloud verification (binding project directive) and report blocking issues
  * Details: .copilot-tracking/details/2026-06-29/auth-enforced-removal-transparent-identity-details.md (Lines 178-186)

## Planning Log

See .copilot-tracking/plans/logs/2026-06-29/auth-enforced-removal-transparent-identity-log.md for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* `uv` (Python backend env + pytest).
* `npx vitest` / `npm` (frontend test + build).
* `azd` (cloud verification per the binding CWYD deploy-and-test directive).
* Azure Easy Auth `/.auth/me` on the frontend origin when identity is enabled (no change required by this work).

## Success Criteria

* `auth_enforced` / `authEnforced` / `AuthBlocked` / "Authentication Not Configured" appear nowhere in `v2/src` or `v2/tests` — Traces to: user requirement "we shouldn't need this variable".
* The SPA resolves identity from `/.auth/me`: principal → real `userId`; no principal → `DEFAULT_USER_ID` ("Guest"); never a blocked screen — Traces to: user requirement "identity enabled → login + userId; else default userId, period".
* `require_admin_auth`, `get_user_id`, `requires_role` unchanged; admin-write protection still engages on operator opt-in — Traces to: research Key Discovery (orthogonality) + operational-safety.
* All backend, shared, and frontend gates green; cloud `/api/health` returns `{status, version, checks}` and the deployed SPA loads guest-by-default with working chat — Traces to: CWYD "every phase ends green" + binding cloud-test directive.
