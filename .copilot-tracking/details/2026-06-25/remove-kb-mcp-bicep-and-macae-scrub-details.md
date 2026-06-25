<!-- markdownlint-disable-file -->
# Implementation Details: Remove KB-MCP Bicep, seed it the reference-architecture way, scrub "macae"

## Context Reference

Sources:
* .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md — primary research: decisive synthesis, selected approach, removal plan, scrub inventory, open decisions D1-D6.
* .copilot-tracking/research/subagents/2026-06-25/macae-kb-mcp-postdeploy-pattern.md — the reference architecture's post-deploy connection-seeding mechanism (script + payload + env vars + CWYD replication fit).
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md — complete `macae` inventory (classified, line-level) + exact Bicep removal plan + git-confirmed pre-Phase-4 value.

Key grounded facts:
* `httpx>=0.28` and `azure-identity>=1.25` are already in v2/pyproject.toml — the seeder needs no new dependency; avoid `azure-ai-projects` runtime discovery by surfacing the project resource id as a Bicep output.
* azd allows ONE `postprovision` hook; it is already wired (v2/azure.yaml ~L223) to v2/scripts/post-provision.{sh,ps1} -> v2/scripts/post_provision.py, which already branches on db mode (pgvector extension in postgresql mode). The cosmosdb-mode KB-MCP seeding is the symmetric branch — no new hook slot, no azure.yaml change.
* CWYD has a single static KB `cwyd-kb`, so the connection name is the deterministic literal `cwyd-kb-mcp` (`'${searchKnowledgeBaseName}-mcp'`).
* Pre-Phase-4 value of `AZURE_AI_SEARCH_CONNECTION_NAME` (git-confirmed) = `aiProjectSearchConnection!.outputs.name` — the base CognitiveSearch connection that 401s. DO NOT revert to it; point at the seeded `cwyd-kb-mcp` instead.
* v2/scripts/post_provision.py's cosmosdb branch ALREADY seeds the Foundry IQ KB inline (`_ensure_search_index`, `_ensure_knowledge_base`, `_build_knowledge_base_seed`) — the connection seed is a SIBLING inline helper there, not a new module.
* The KB seed uses the SEARCH data-plane scope (`https://search.azure.com/.default`, `SEARCH_DATA_PLANE_SCOPE`); the connection PUT needs the ARM control-plane scope (`https://management.azure.com/.default`) — different planes.
* `aiProject.outputs.resourceId` exists (v2/infra/modules/ai-project.bicep L80) and `AZURE_AI_SEARCH_ENDPOINT` is already a main.bicep output (L2535) — Step 2.2 only adds one project-resource-id output; no ai-project module edit.

## Implementation Phase 1: KB-MCP connection seeder helper in post_provision.py

<!-- parallelizable: true -->

### Step 1.1: Add the `_ensure_kb_mcp_connection` helper + test

The cosmosdb branch of v2/scripts/post_provision.py already seeds the Foundry IQ KB with inline idempotent `httpx` PUT helpers (`_ensure_search_index`, `_ensure_knowledge_base`). Add a SIBLING inline helper `_ensure_kb_mcp_connection` next to them — do NOT create a new standalone module/shim (the KB seed is inline, so the connection seed is inline too: consistency, least new surface).

Helper shape (mirror `_ensure_knowledge_base(*, dry_run, client_factory=None) -> str` exactly — same `client_factory` test seam + `"skipped"` / `"dry-run"` / `"ensured"` return contract):
* Reads env as the SINGLE SOURCE OF TRUTH (DR-06): `AZURE_AI_PROJECT_RESOURCE_ID` (new output from Step 2.2), `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME` (the SAME var `_ensure_knowledge_base` reads — the connection name is `f"{kb_name}-mcp"`, so it cannot drift from the Bicep env wiring `'${searchKnowledgeBaseName}-mcp'`), `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION`.
* New module-level constants beside the existing scope constants: `ARM_SCOPE = "https://management.azure.com/.default"` (the connection PUT is a CONTROL-plane call — distinct from the `SEARCH_DATA_PLANE_SCOPE` the KB seed uses) and `KB_MCP_CONNECTION_API_VERSION = "2025-04-01-preview"`.
* Returns `"skipped"` when `AZURE_AI_SEARCH_ENDPOINT` or `AZURE_AI_PROJECT_RESOURCE_ID` is unset (postgresql mode), `"dry-run"` under `--dry-run`, `"ensured"` otherwise.
* Payload: the RemoteTool `properties` from the research Complete Examples, built as a plain `dict` (externally-owned REST body — the Hard Rule #15 boundary carve-out, matching `_build_knowledge_base_seed`'s plain-dict precedent):
  ```jsonc
  {
    "category": "RemoteTool",
    "target": "{AZURE_AI_SEARCH_ENDPOINT}/knowledgebases/{kb}/mcp?api-version={kb_api_version}",
    "authType": "ProjectManagedIdentity",
    "useWorkspaceManagedIdentity": true,
    "isSharedToAll": true,
    "audience": "https://search.azure.com",
    "metadata": { "ApiType": "Azure" }
  }
  ```
* PUT `https://management.azure.com{project_resource_id}/connections/{kb}-mcp?api-version={KB_MCP_CONNECTION_API_VERSION}` with an ARM bearer (`DefaultAzureCredential().get_token(ARM_SCOPE)`), via `httpx`. Idempotent (create-or-update): HTTP 200/201 = `"ensured"`; any other status -> stderr/log + raise per Hard Rule #14 (mirror `_ensure_knowledge_base`'s error handling).

Test (extend v2/tests/scripts/test_post_provision.py, mirroring the `_ensure_knowledge_base` tests): the `client_factory` seam, payload shape, PUT URL + api-version + ARM scope, `"skipped"` with no endpoint, `--dry-run` makes no HTTP call, non-2xx re-raise.

Files:
* v2/scripts/post_provision.py - add `_ensure_kb_mcp_connection` + the two constants (no new module).
* v2/tests/scripts/test_post_provision.py - add the helper's tests (test-first, Hard Rule #2).

Discrepancy references:
* Implements the selected approach (research Scenario 1) inline, consistent with the existing KB-seed helpers; resolves DR-01 (project id via Bicep output) + DR-06 (single-source KB name).

Success criteria:
* The payload + URLs match the research Complete Examples / Configuration Examples exactly; the ARM scope is distinct from the search data-plane scope.
* `uv run python -m pytest v2/tests/scripts/test_post_provision.py` runs (passes or fails with a clear assertion).
* No new file under v2/scripts; no new entry in v2/pyproject.toml (httpx + azure-identity already present).

Context references:
* v2/scripts/post_provision.py (the `_ensure_knowledge_base` / `_build_knowledge_base_seed` helpers) - the inline-helper + plain-dict-REST-body pattern to mirror.
* .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md (Key Discoveries — Complete Examples / API and Schema) - exact payload + URLs + api-versions.

Dependencies:
* None (httpx + azure-identity already in pyproject). Phase 3 wires the call.

### Step 1.2: Validate phase changes

Run the post_provision tests only (isolated; no infra edits yet).

Validation commands:
* `uv run python -m pytest v2/tests/scripts/test_post_provision.py` - the new helper's unit tests.

## Implementation Phase 2: Bicep — remove module, rewire env, surface project resource id

<!-- parallelizable: false -->

### Step 2.1: Delete the module file + its main.bicep call + rewire the env var

Per the research removal plan (subagent inventory Goal B):
* DELETE v2/infra/modules/ai-project-kb-mcp-connection.bicep.
* DELETE v2/infra/main.bicep lines 1061-1076 (the leading comment block + the `module aiProjectKbMcpConnection ... = if (databaseType == 'cosmosdb') { ... }` block). KEEP `aiProjectSearchConnection` (the base CognitiveSearch connection, ~L1048-1059).
* CHANGE v2/infra/main.bicep L1881 from `value: databaseType == 'cosmosdb' ? aiProjectKbMcpConnection!.outputs.name : ''` to `value: databaseType == 'cosmosdb' ? '${searchKnowledgeBaseName}-mcp' : ''` (the deterministic seeded connection name — NOT the base connection).

Files:
* v2/infra/modules/ai-project-kb-mcp-connection.bicep - DELETE (use `git rm` / terminal `Remove-Item`; do not blank the file).
* v2/infra/main.bicep - remove module block L1061-1076; rewire env L1881.

Discrepancy references:
* DD-01 (the env-revert trap): we deviate from a literal pre-Phase-4 revert because reverting to `aiProjectSearchConnection!.outputs.name` re-opens BUG-0025/0059.

Success criteria:
* `aiProjectKbMcpConnection` and `ai-project-kb-mcp-connection` no longer appear in v2/infra/main.bicep.
* `AZURE_AI_SEARCH_CONNECTION_NAME` resolves to `'${searchKnowledgeBaseName}-mcp'` in cosmosdb mode.

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (Goal B — B.1/B.2/B.3) - exact lines + the git-confirmed prior value.

Dependencies:
* None on Phase 1 files, but ordered after Phase 1 so the connection has a creator before the env points at it.

### Step 2.2: Surface the Foundry project ARM resource id as an output

The seeder needs the project's ARM resource id for the PUT URL. Avoid runtime discovery by emitting it from Bicep:
* Add `output AZURE_AI_PROJECT_RESOURCE_ID string = aiProject.outputs.resourceId` (the `aiProject` module already exposes `resourceId` — confirmed at v2/infra/modules/ai-project.bicep L80 — so NO ai-project module edit is needed) near the existing AZURE_AI_* outputs (~L2541 region).
* `AZURE_AI_SEARCH_ENDPOINT` is ALREADY an output (v2/infra/main.bicep L2535, cosmosdb-gated) — no change; the seeder reads both from the azd env.

Files:
* v2/infra/main.bicep - add the `AZURE_AI_PROJECT_RESOURCE_ID` output only.

Success criteria:
* `azd env get-values` (post-provision, cosmosdb mode) exposes `AZURE_AI_PROJECT_RESOURCE_ID` + `AZURE_AI_SEARCH_ENDPOINT`.

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-kb-mcp-postdeploy-pattern.md (Env vars required) - the script's required inputs.

Dependencies:
* Step 2.1 (same file).

### Step 2.3: Rebuild ARM + validate

Files:
* v2/infra/main.json - regenerated (do not hand-edit).

Validation commands:
* `az bicep build --file <ABS path>\v2\infra\main.bicep` - must exit 0 (pre-existing BCP081/BCP334 warnings only).

Dependencies:
* Steps 2.1, 2.2.

## Implementation Phase 3: Wire the seeder into post_provision.py (cosmosdb branch)

<!-- parallelizable: false -->

### Step 3.1: Wire the connection seed into the cosmosdb branch (after the KB seed)

In v2/scripts/post_provision.py's cosmosdb path, call `_ensure_kb_mcp_connection(dry_run=...)` immediately AFTER the existing `_ensure_knowledge_base(...)` call (DR-05: KB first, then its `{kb}-mcp` connection — coherent flow, matches the reference architecture's order). The helper already returns `"skipped"` in postgresql mode, so no extra gating is needed beyond the existing branch.

RBAC prerequisite (DR-04): the connection PUT is an ARM control-plane write (`Microsoft.CognitiveServices/accounts/projects/connections/write`). The deploy principal that runs `azd provision` previously created this exact connection via the now-deleted Bicep module, so it already holds the right under the standard interactive / SP deployer (Owner/Contributor). post_provision.py runs `continueOnError: false`, so document this as a deploy prerequisite in the summary + worklog and surface the optional robust alternative (an explicit Bicep role assignment) as PD-04 — do NOT silently swallow a 403 (Hard Rule #14).

Files:
* v2/scripts/post_provision.py - add the `_ensure_kb_mcp_connection(...)` call after `_ensure_knowledge_base(...)` in the cosmosdb branch.
* v2/tests/scripts/test_post_provision.py - assert the cosmosdb branch calls the connection seed (after the KB seed) and the pgvector branch does not.

Discrepancy references:
* DD-02: postprovision hook home (D1). DR-04 (RBAC prerequisite). DR-05 (ordering).

Success criteria:
* In cosmosdb mode `_ensure_kb_mcp_connection` is invoked once, after the KB seed; in pgvector mode it returns `"skipped"`.
* `uv run python -m pytest v2/tests/scripts/test_post_provision.py` passes.

Context references:
* v2/azure.yaml (Lines ~198-240) - the existing postprovision hook (no edit needed).
* v2/scripts/post_provision.py (the cosmosdb branch in `main()`) - the call site after `_ensure_knowledge_base`.

Dependencies:
* Phase 1 (the helper), Phase 2 (the `AZURE_AI_PROJECT_RESOURCE_ID` output).

### Step 3.2: Validate phase changes

Validation commands:
* `uv run python -m pytest v2/tests/scripts/test_post_provision.py`

Dependencies:
* Step 3.1.

## Implementation Phase 4: Scrub — infra + config comments

<!-- parallelizable: false -->

### Step 4.1: Reword the `macae` comments in infra + config

Sequenced after Phase 2/3 because it edits v2/infra/main.bicep again. Apply the neutral-replacement convention ("the read-only reference architecture" / "reference-architecture pattern"). The two kb-mcp-module matches are already gone (file deleted in Phase 2).

Files:
* v2/infra/main.bicep - reword comments at L289, L1596, L1776, L1949, L2014, L2031, L2252 (line numbers shift after Phase 2 deletions; re-locate by text).
* v2/infra/modules/virtualNetwork.bicep - L27 (drop the named external repo path too).
* v2/azure.yaml - L118 comment.
* v2/.env - L50 comment (drop the external script name).

Discrepancy references:
* PD-02 (D4): external sample paths — default keep technical paths, drop only the proper noun, EXCEPT virtualNetwork.bicep L27 / .env L50 where the path IS the reference and is reworded.

Success criteria:
* `grep -i macae v2/infra v2/azure.yaml v2/.env` returns zero matches.

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (NEW-INFRA + V2-ENV sections) - exact lines + proposed replacements.

Dependencies:
* Phase 2 (main.bicep must be in its post-removal state first).

## Implementation Phase 5: Scrub — backend source

<!-- parallelizable: true -->

### Step 5.1: Reword `macae` in backend production code

Files:
* v2/src/backend/core/agents/definitions.py - L23, L37, L154 (reword; the L154 "MACAE pattern (common/utils/utils_af.py ...)" — drop the proper noun; keep/drop the external path per PD-02).
* v2/src/backend/core/tools/content_safety.py - L21, L22, L156, L160.

Success criteria:
* `grep -i macae v2/src/backend` returns zero matches; backend tests unaffected (comments only).

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (V2-SRC — backend) - exact lines + replacements.

Dependencies:
* None (independent file area).

## Implementation Phase 6: Scrub — frontend source

<!-- parallelizable: true -->

### Step 6.1: Reword `macae` in frontend production code (+ Phase-header tails)

Apply the neutral reword; for `Phase: 4 (... MACAE re-skin ...)` header tails apply D3 (trim to the standing phase name, which also satisfies Hard Rule #16).

Files:
* v2/src/frontend/src/theme/tokens.css, FluentThemeBridge.tsx
* v2/src/frontend/src/pages/chat/** (MessageList.tsx/.module.css, MessageInput.tsx/.module.css, HistoryPanel.tsx/.module.css, ChatPage.tsx/.module.css)
* v2/src/frontend/src/components/Header/** (userIdentity.tsx, MultiAgentLogo.tsx, MsftColorLogo.tsx, HeaderTools.tsx, Header.tsx, Header.module.css)
* v2/src/frontend/src/components/CoralShell/** (PanelLeft.tsx, CoralShellRow.tsx, CoralShellColumn.tsx, CoralShell.module.css)

Discrepancy references:
* DD-03 / PD-03 (D3): header-tail trim vs reword.

Success criteria:
* `grep -i macae v2/src/frontend` returns zero matches; `npm test` (frontend) unaffected (comments only, except the Phase-header tests in Phase 7).

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (V2-SRC — frontend) - exact lines + replacements.

Dependencies:
* None (independent file area).

## Implementation Phase 7: Scrub — tests (incl. one rename)

<!-- parallelizable: true -->

### Step 7.1: Reword test docstrings + rename the one test

Files:
* v2/tests/backend/core/agents/test_definitions.py - L10 docstring; RENAME `test_rai_agent_uses_macae_classifier_pattern` -> `test_rai_agent_uses_classifier_pattern` (L260) + L261 docstring.
* v2/tests/frontend/theme/FluentThemeBridge.test.tsx - L3 Phase header.
* v2/tests/frontend/components/PanelLeft.test.tsx, MultiAgentLogo.test.tsx, Header.test.tsx (L3, L8, L49), CoralShell.test.tsx - Phase headers + the L8/L49 wording.

Discrepancy references:
* Test rename is low-risk per Hard Rule #11 (test function name, not shipped API).

Success criteria:
* `grep -i macae v2/tests` returns zero matches.
* `uv run python -m pytest v2/tests/backend/core/agents/test_definitions.py` passes (renamed test still asserts the TRUE/FALSE classifier shape).
* Frontend tests still pass.

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (V2-TESTS) - exact lines + the rename target.

Dependencies:
* Coordinate with Phase 5/6 only if a test asserts on a reworded source string (none identified — comments are not asserted).

## Implementation Phase 8: Scrub — bugs.md attribution

<!-- parallelizable: true -->

### Step 8.1: Reword the proper-noun attribution in bugs.md (keep all technical content)

Reword "MACAE" -> "the read-only reference architecture" on lines 83, 105, 130, 131, 411, 508, 521, 523, 851, 1222, 1237; KEEP every technical fact (connection category, payload fields, role grants, audience). Also correct the stale KB-MCP target api-version where bugs.md says `2025-05-01-preview` to `2025-11-01-preview`.

Files:
* v2/docs/bugs.md - reword the 11 attribution lines; fix the stale api-version.

Discrepancy references:
* DR-02: bugs.md is a durable defect registry (Hard Rule #19) — attribution wording only, no technical-content edits.

Success criteria:
* `grep -i macae v2/docs/bugs.md` returns zero matches; all `RemoteTool`/`ProjectManagedIdentity`/`audience`/role-grant technical detail preserved.

Context references:
* .copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md (V2-DOCS-BUGS) - per-line rewordings.

Dependencies:
* None (independent file).

## Implementation Phase 9: Validation

<!-- parallelizable: false -->

### Step 9.1: Run full project validation

Validation commands:
* `az bicep build --file <ABS path>\v2\infra\main.bicep` - exit 0 (pre-existing BCP081/BCP334 only).
* `uv run python -m pytest` (from v2/) - full backend + scripts suite green.
* `npm test` (from v2/) - frontend vitest green.
* `grep -ri macae v2/src v2/infra v2/tests v2/azure.yaml v2/.env v2/docs/bugs.md` - ZERO matches (the agreed scope). REPO-GOVERNANCE, TRACKING, SAMPLE-FOLDER, and (per PD-01 default) v2/docs ADRs+worklogs are intentionally excluded.
* Convention gates (e.g. test_no_process_narrative_in_src, test_init_files_are_marker_only) still pass.

### Step 9.2: Fix minor validation issues

Iterate on lint/test/grep misses. Apply straightforward fixes directly.

### Step 9.3: Report blocking issues + hand off cloud verification

* Cloud `azd up` smoke (cosmosdb then postgresql) is operator-owned: confirm the seeder creates `cwyd-kb-mcp` at postprovision, grounding works with zero manual `az`, and pgvector mode no-ops the seeder.
* Document any blocking issue and recommend follow-on planning rather than large inline fixes.

## Dependencies

* Python: `uv sync` (httpx + azure-identity already present).
* Azure CLI with Bicep (`az bicep build`).
* Node/npm for frontend vitest.

## Success Criteria

* The Bicep `RemoteTool` module is gone; the connection is created at postprovision by the seeder; `AZURE_AI_SEARCH_CONNECTION_NAME` -> `cwyd-kb-mcp`.
* `grep -ri macae` is zero across the agreed shipped-artifact scope.
* BUG-0025/0059 stays fixed; `azd up` needs no manual `az`.
* All local gates green (bicep build, pytest, vitest, convention gates).
