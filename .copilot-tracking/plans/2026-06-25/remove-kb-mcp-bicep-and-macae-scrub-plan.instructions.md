---
applyTo: '.copilot-tracking/changes/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: Remove KB-MCP Bicep, seed it the reference-architecture way, scrub "macae"

## Overview

Replace the rejected Bicep `RemoteTool` connection with an idempotent post-provision seeder (reference-architecture mechanism), keep grounding working by pointing `AZURE_AI_SEARCH_CONNECTION_NAME` at the seeded `cwyd-kb-mcp` connection, and scrub every `macae` reference from CWYD's shipped artifacts.

## Objectives

### User Requirements

* Remove `v2/infra/modules/ai-project-kb-mcp-connection.bicep` ("this file is not valid ... we should remove") — Source: user 2026-06-25.
* Create the KB-MCP connection "the same way the reference architecture does ... standardize our deployment behavior" (a post-deploy/provision script, not Bicep) — Source: user 2026-06-25 (kb-mcp-fix free-text).
* "We shouldn't have any reference to macae" — full scrub, incl. `v2/docs/bugs.md` + the test name — Source: user 2026-06-25 (macae-scope = full scrub).

### Derived Objectives

* Do NOT literally revert the env var to the base `CognitiveSearch` connection — Derived from: that connection 401s (BUG-0025/0059); reverting re-opens the defect (research decisive synthesis).
* Keep the deploy one-shot (`azd up`, no manual `az`) — Derived from: prior "single azd up" goal; the seeder runs in the existing auto-running postprovision hook.
* Preserve bugs.md technical content + governance/tracking citations — Derived from: Hard Rule #19 (durable registry) + Hard Rule #9 (sanctioned reference) — reword attribution only; keep ADRs/worklogs (PD-01 default).

## Context Summary

### Project Files

* v2/infra/main.bicep - delete the kb-mcp module call (L1061-1076); rewire `AZURE_AI_SEARCH_CONNECTION_NAME` (L1881); add a project-resource-id output; scrub comments.
* v2/infra/modules/ai-project-kb-mcp-connection.bicep - DELETE.
* v2/scripts/post_provision.py - add `_ensure_kb_mcp_connection` inline helper (idempotent ARM PUT, sibling of `_ensure_knowledge_base`); call it in the cosmosdb branch after the KB seed.
* v2/tests/scripts/test_post_provision.py - extend with the helper's tests.
* v2/azure.yaml - no hook change (postprovision already wired); scrub one comment.
* v2/src/backend/**, v2/src/frontend/**, v2/tests/**, v2/.env, v2/docs/bugs.md - `macae` scrub.

### References

* .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md - primary research (synthesis, approach, decisions D1-D6).
* .copilot-tracking/research/subagents/2026-06-25/macae-kb-mcp-postdeploy-pattern.md - the seeding mechanism + payload + env vars.
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md - classified `macae` inventory + exact removal plan + git-confirmed prior value.

### Standards References

* .github/copilot-instructions.md - Hard Rules #1 (one unit/turn), #2 (test-first), #9 (sanctioned reference), #14 (SDK resilience), #15 (typed payload), #16 (no process narrative), #19 (durable registries).
* .github/instructions/v2-infra.instructions.md, v2-tests.instructions.md - Bicep/azd + test conventions.

## Implementation Checklist

### [x] Implementation Phase 1: KB-MCP connection seeder helper in post_provision.py

<!-- parallelizable: true -->

* [x] Step 1.1: Add `_ensure_kb_mcp_connection` inline helper + test (ARM PUT; sibling of `_ensure_knowledge_base`)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 1.1)
* [x] Step 1.2: Validate (`pytest test_post_provision.py`)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 1.2)

### [x] Implementation Phase 2: Bicep — remove module, rewire env, surface project id

<!-- parallelizable: false -->

* [x] Step 2.1: Delete the module file + main.bicep call + rewire env L1881 to `'${searchKnowledgeBaseName}-mcp'`
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 2.1)
* [x] Step 2.2: Surface `AZURE_AI_PROJECT_RESOURCE_ID` output (reuse `aiProject.outputs.resourceId`)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 2.2)
* [x] Step 2.3: Rebuild ARM (`az bicep build`) + validate
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 2.3)

### [x] Implementation Phase 3: Wire the connection seed into the cosmosdb branch (after the KB seed)

<!-- parallelizable: false -->

* [x] Step 3.1: Call `_ensure_kb_mcp_connection` after `_ensure_knowledge_base` (DR-05 order) + RBAC prerequisite note (DR-04) + test
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 3.1)
* [x] Step 3.2: Validate (`pytest test_post_provision.py`)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 3.2)

### [x] Implementation Phase 4: Scrub — infra + config comments

<!-- parallelizable: false -->

* [x] Step 4.1: Reword `macae` in main.bicep / virtualNetwork.bicep / azure.yaml / .env
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 4.1)

### [x] Implementation Phase 5: Scrub — backend source

<!-- parallelizable: true -->

* [x] Step 5.1: Reword `macae` in definitions.py + content_safety.py
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 5.1)

### [x] Implementation Phase 6: Scrub — frontend source

<!-- parallelizable: true -->

* [x] Step 6.1: Reword `macae` + trim Phase-header tails (theme / chat / Header / CoralShell)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 6.1)

### [x] Implementation Phase 7: Scrub — tests (incl. one rename)

<!-- parallelizable: true -->

* [x] Step 7.1: Reword docstrings + rename `test_rai_agent_uses_macae_classifier_pattern`
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 7.1)

### [x] Implementation Phase 8: Scrub — bugs.md attribution

<!-- parallelizable: true -->

* [x] Step 8.1: Reword attribution (keep technical content) + fix stale api-version
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 8.1)

### [x] Implementation Phase 9: Validation

<!-- parallelizable: false -->

* [x] Step 9.1: Full validation (bicep build, pytest, vitest, `grep -ri macae` = 0 in scope, convention gates)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 9.1)
* [x] Step 9.2: Fix minor validation issues
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 9.2)
* [x] Step 9.3: Report blocking issues + hand off cloud `azd up` smoke (operator)
  * Details: .copilot-tracking/details/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-details.md (Step 9.3)

## Planning Log

See .copilot-tracking/plans/logs/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-log.md for discrepancy tracking, implementation paths considered, planning decisions (PD-01..03), and suggested follow-on work.

## Dependencies

* `uv sync` (httpx + azure-identity already in v2/pyproject.toml — no new dep).
* Azure CLI + Bicep (`az bicep build`).
* Node/npm (frontend vitest).

## Success Criteria

* `v2/infra/modules/ai-project-kb-mcp-connection.bicep` deleted; `main.bicep` builds clean; `AZURE_AI_SEARCH_CONNECTION_NAME` -> `cwyd-kb-mcp` — Traces to: user requirement 1 + decisive synthesis.
* The `cwyd-kb-mcp` connection is created automatically at postprovision in cosmosdb mode; no-op in pgvector; no manual `az` — Traces to: user requirement 2 (reference-architecture parity).
* `grep -ri macae` zero across v2/src, v2/infra, v2/tests, v2/azure.yaml, v2/.env, v2/docs/bugs.md — Traces to: user requirement 3 (full scrub, agreed scope).
* BUG-0025/0059 stays fixed; all local gates green — Traces to: derived objective (don't re-open the defect).
