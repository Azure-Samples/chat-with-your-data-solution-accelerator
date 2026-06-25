<!-- markdownlint-disable-file -->
# Task Research: Remove the Bicep KB-MCP connection, adopt MACAE's post-deploy mechanism, and scrub every "macae" reference

The operator rejected the durable Bicep approach for the `cwyd-kb-mcp` Foundry Project RemoteTool connection (`v2/infra/modules/ai-project-kb-mcp-connection.bicep`, added in "Phase 4"). Two directives:

1. **Remove** `v2/infra/modules/ai-project-kb-mcp-connection.bicep` and revert its `main.bicep` wiring. The operator calls it "not valid" — not a syntax error (`az bicep build` is clean) but the wrong *mechanism*.
2. **Handle the KB MCP connection the same way MACAE does** — "we are trying to standardize our deployment behavior." MACAE creates the connection at **post-deploy** via a script (`infra/scripts/seed_kb_connections.py`), not as a Bicep resource.
3. **Full scrub** — rewrite every `macae` mention in the v2 codebase (production code, infra comments, `v2/docs/bugs.md`, the `test_rai_agent_uses_macae_classifier_pattern` test name, the `.env` comment) so the shipped artifacts carry no reference to the external sample.

## Task Implementation Requests

* Delete `v2/infra/modules/ai-project-kb-mcp-connection.bicep` and its module call in `v2/infra/main.bicep` (~L1061-1076).
* **Do NOT** literally revert `AZURE_AI_SEARCH_CONNECTION_NAME` (L1881) to the pre-Phase-4 value `aiProjectSearchConnection!.outputs.name` — that is the base `CognitiveSearch` connection that 401s (BUG-0025/0059). Instead point it at the deterministic name the new seeder creates: `databaseType == 'cosmosdb' ? '${searchKnowledgeBaseName}-mcp' : ''` (i.e. the static `cwyd-kb-mcp`).
* Replace the Bicep mechanism with a reference-architecture-style post-deploy connection-seeding step (azd hook + a thin Python script, mirroring CWYD's existing `upload_sample_data.py` shim style), described in neutral terms (no "macae" naming).
* Scrub every `macae` reference in shipped artifacts per the inventory below, using neutral replacements ("the read-only reference architecture", or describe the pattern without naming it).

## Scope and Success Criteria

* Scope: `v2/**` production code, infra, docs, tests, and the gitignored `.env` comment; the new "Phase 4" Bicep artifact; the post-deploy seeding mechanism. **Open scope decisions** (flagged, not assumed): whether the scrub also touches repo governance (`.github/copilot-instructions.md`, `.github/instructions/**`), the `.copilot-tracking/**` planning history, and the `data/sample_code/macae/**` reference folder itself.
* Assumptions:
  * "Same way as MACAE" = a post-deploy script invoked by an azd hook that PUTs the `{kb}-mcp` `RemoteTool`/`ProjectManagedIdentity` connection — confirmed against `data/sample_code/macae/infra/scripts/seed_kb_connections.py` (pending subagent read).
  * The neutral scrub must not destroy the *technical* root-cause content in `v2/docs/bugs.md` (the connection-category fix is real and load-bearing) — only the literal "macae" attribution is reworded.
* Success Criteria:
  * `v2/infra/modules/ai-project-kb-mcp-connection.bicep` no longer exists; `main.bicep` builds clean with the module removed.
  * `AZURE_AI_SEARCH_CONNECTION_NAME` resolves to the deterministic `cwyd-kb-mcp` name (NOT the base `CognitiveSearch` connection), so grounding still works.
  * The KB MCP connection is created automatically at deploy time by a post-deploy step (no manual `az` follow-up) — matching the reference architecture's *mechanism* while keeping CWYD's auto-running-hook convention.
  * `grep -ri "macae" v2/` returns zero matches in the agreed shipped-artifact scope (V2-SRC, NEW-INFRA, V2-ENV, V2-TESTS, bugs.md attribution).
  * BUG-0025/0059 stays fixed (the `RemoteTool`/`ProjectManagedIdentity`/`audience` connection still gets created, just by script not Bicep).

## Outline

1. KB-MCP connection mechanism: the reference architecture seeds it with a **post-deploy script** (`seed_kb_connections.py`), not Bicep. CWYD should mirror that mechanism with a thin `uv`-shim script like its existing `upload_sample_data.py`.
2. The decisive synthesis: removing the Bicep module is correct, but the env var must point at the **script-created** `cwyd-kb-mcp` connection, NOT be reverted to the base `CognitiveSearch` connection (which 401s).
3. Exact Bicep removal plan (module file + `main.bicep` L1061-1076 + L1881 rewire) — no orphaned params, no tests broken.
4. Complete `macae` scrub inventory, classified, with neutral replacements + open scope decisions.
5. A security flag: the sample's `.azure/**` logs carry real subscription/RG identifiers.

## Potential Next Research

* Confirm `httpx` + `azure-identity` are already in `v2/pyproject.toml` (avoid adding `azure-ai-projects` by surfacing the project resource id / endpoint as a Bicep output instead of MACAE's runtime discovery).
  * Reasoning: lets the seeder be a dependency-free thin script.
  * Reference: subagent `macae-kb-mcp-postdeploy-pattern.md` §CWYD replication fit.
* Confirm the deploy identity holds `Azure AI User` (or `Microsoft.CognitiveServices/.../connections/write`) on the Foundry account, else the PUT 403s.
  * Reference: same subagent, gap #5.
* If the operator opts to scrub `v2/docs/**` ADRs + worklogs, do a full line-level enumeration first (the sweep was capped at 80).

## Research Executed

### File Analysis

* `v2/infra/modules/ai-project-kb-mcp-connection.bicep` (full) — the `RemoteTool` / `ProjectManagedIdentity` / `audience` connection via `any(...)`; params `knowledgeBaseName='cwyd-kb'`, `connectionName='${knowledgeBaseName}-mcp'`. Self-contained; nothing outside references it except the module call.
* `v2/infra/main.bicep` L1048-1076 — `aiProjectSearchConnection` (base CognitiveSearch, L1048-1059, STAYS) then `aiProjectKbMcpConnection` (L1061-1076, DELETE). L1881 env wiring. `searchKnowledgeBaseName` param L193; `searchKnowledgeBaseApiVersion` param L199 (still used at L1876 app-setting + L2547 output — NOT orphaned).
* `data/sample_code/macae/infra/scripts/post-provision/seed_kb_connections.py` (full) — ARM-plane `PUT .../connections/{kb}-mcp?api-version=2025-04-01-preview`; `DefaultAzureCredential`; idempotent (200/201/409 ok); KB names static from `seed_knowledge_bases.py`.
* `v2/scripts/upload_sample_data.py` + `upload-sample-data.{sh,ps1}` — CWYD's existing post-deploy shim convention (thin `uv run python` wrapper, `DefaultAzureCredential`, idempotent, trigger-aware, no-op gates). The new seeder should mirror this exactly.

### Code Search Results

* `macae` (case-insensitive, whole workspace) — classified totals: V2-SRC 41, NEW-INFRA 11 (+2 in deleted file), V2-ENV 1, V2-TESTS 10, V2-DOCS-BUGS 11, V2-OTHER (ADRs+worklogs) 80+, REPO-GOVERNANCE 10, TRACKING 200+, SAMPLE-FOLDER hundreds. v1 `code/**` + root docs/infra/tests = 0.
* `aiProjectKbMcpConnection|ai-project-kb-mcp|kbMcpConnection` — only in `main.bicep` (L1067/1068/1881), generated `main.json`, the module file, and tracking docs. **No `v2/tests` reference** — deletion breaks no test.
* Pre-Phase-4 value of `AZURE_AI_SEARCH_CONNECTION_NAME` (git `log -p -S`): `aiProjectSearchConnection!.outputs.name` — the base CognitiveSearch connection (the BUG-0025/0059 401 path; see synthesis).

### External Research

* Reference architecture (read-only clone at `data/sample_code/macae/`): seeds per-KB `RemoteTool` connections from a post-deploy script because its KB names are *dynamic per content pack*. CWYD has a single static KB (`cwyd-kb`) → the connection name `cwyd-kb-mcp` is known at author time, so CWYD's env wiring can hard-reference it without runtime discovery.

### Project Conventions

* Standards referenced: `.github/copilot-instructions.md` Hard Rules — #4 (registry dispatch, N/A here), #9 (reference architecture is a sanctioned read-only source — governs the scrub KEEP decision), #14 (SDK boundary resilience for the seeder's PUT), #16 (no process narrative; the `Phase: 4 (... MACAE re-skin)` header tails are a two-birds fix), #18 + user `azure-env-ids` memory (the sample `.azure/**` real-id leak), #19 (worklogs are durable dated history).
* Instructions followed: `v2-infra.instructions.md` (Bicep + azd hooks), `python-script` + `uv-projects` (the seeder script).

## Key Discoveries

### The decisive synthesis (read this first)

"Remove the Bicep file" + "handle the KB MCP the same way the reference architecture does" do **not** mean "revert to pre-Phase-4." The pre-Phase-4 state pointed `AZURE_AI_SEARCH_CONNECTION_NAME` at the base `CognitiveSearch` connection, which is the exact wrong-category connection that returns `401` on `/knowledgebases/.../mcp` (BUG-0025/0059). The correct end state keeps the *same outcome* (`AZURE_AI_SEARCH_CONNECTION_NAME` → the `cwyd-kb-mcp` `RemoteTool` connection) but changes the *creation mechanism* from a Bicep resource to a post-deploy script. Because CWYD's KB is static, the connection name is the deterministic literal `cwyd-kb-mcp` (`'${searchKnowledgeBaseName}-mcp'`), so Bicep wires the env var to that string and the script guarantees a connection of that name exists.

### Project Structure

* The base `CognitiveSearch` connection (`aiProjectSearchConnection`) STAYS in Bicep — it is the base search connection (the reference architecture keeps an equivalent base connection in Bicep too). Only the `RemoteTool` connection moves to the script.
* New files mirror the existing post-deploy uploader trio: `v2/scripts/seed_kb_connections.py` + `v2/scripts/seed-kb-connections.sh` + `.ps1`.

### Implementation Patterns

* Seeder = thin script: `DefaultAzureCredential` → ARM token (`https://management.azure.com/.default`) → `httpx.put` the connection; treat 200/201/409 as success (idempotent); **no-op when `databaseType != cosmosdb`** (pgvector has no Foundry IQ KB); structured logging + re-raise per Hard Rule #14.
* Project resource id: prefer a clean Bicep **output** (e.g. the Foundry project resource id or endpoint) surfaced into the azd env, instead of the reference architecture's runtime data-plane discovery — CWYD's project is static and already an output-friendly symbol (`aiProject.outputs.*`).
* Hook: an azd `postprovision` (or `postdeploy`) hook that runs the shim automatically. Unlike the reference architecture's banner+manual driver, CWYD's hooks already auto-run (`upload_sample_data`), which is what actually delivers "single `azd up`, no manual `az`."

### Complete Examples

Seeder PUT payload (identical to the deleted Bicep `properties`, now sent by the script):

```jsonc
// PUT https://management.azure.com{projectResourceId}/connections/cwyd-kb-mcp?api-version=2025-04-01-preview
{
  "properties": {
    "category": "RemoteTool",
    "target": "{AZURE_AI_SEARCH_ENDPOINT}/knowledgebases/cwyd-kb/mcp?api-version=2025-11-01-preview",
    "authType": "ProjectManagedIdentity",
    "useWorkspaceManagedIdentity": true,
    "isSharedToAll": true,
    "audience": "https://search.azure.com",
    "metadata": { "ApiType": "Azure" }
  }
}
```

### API and Schema Documentation

* Connection PUT api-version: `2025-04-01-preview` (control plane). KB-MCP target-URL api-version: `2025-11-01-preview`. (bugs.md's old `2025-05-01-preview` target version is stale — correct to `2025-11-01-preview` during the scrub edit of bugs.md.)
* Required role for the PUT caller (the deploy identity): `Azure AI User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) on the Foundry account, or any role granting `Microsoft.CognitiveServices/accounts/projects/connections/write`.

### Configuration Examples

Env wiring (replaces the deleted-module reference at `main.bicep` L1881):

```bicep
{ name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? '${searchKnowledgeBaseName}-mcp' : '' }
```

## Technical Scenarios

### Scenario 1 — KB MCP connection creation mechanism

The operator wants the Bicep `RemoteTool` connection gone and the connection created "the same way" the reference architecture does, to standardize deployment.

**Requirements:**

* Connection created automatically during `azd up` (no manual `az`).
* `AZURE_AI_SEARCH_CONNECTION_NAME` resolves to the `cwyd-kb-mcp` `RemoteTool` connection (grounding stays fixed).
* No-op cleanly in pgvector mode.
* No "macae" naming in the shipped script/comments.

**Preferred Approach — post-deploy seeder script (auto-run hook):**

* New `v2/scripts/seed_kb_connections.py` (+ `.sh`/`.ps1` shims) idempotently PUTs `cwyd-kb-mcp` using the payload above; gated to cosmosdb mode; mirrors `upload_sample_data.py` conventions.
* azd hook (postprovision or postdeploy) runs it automatically.
* Bicep: delete the `RemoteTool` module, keep the base `CognitiveSearch` connection, set `AZURE_AI_SEARCH_CONNECTION_NAME` to `'${searchKnowledgeBaseName}-mcp'`.
* Surface the Foundry project resource id (or endpoint) + search endpoint as azd env values the script reads.

```text
v2/
  scripts/
    seed_kb_connections.py        (NEW)
    seed-kb-connections.sh        (NEW)
    seed-kb-connections.ps1       (NEW)
  infra/
    main.bicep                    (MODIFY: delete module L1061-1076; rewire L1881; maybe add project-id output)
    modules/
      ai-project-kb-mcp-connection.bicep   (DELETE)
  azure.yaml                      (MODIFY: add seeder hook)
```

**Implementation Details:** see Complete Examples + Configuration Examples above; resilience per Hard Rule #14; tests mirror `v2/tests/scripts/test_upload_sample_data.py` (payload shape, cosmosdb-gate no-op, idempotent 409 handling).

#### Considered Alternatives

* **Keep the Bicep `RemoteTool` resource (current Phase 4).** Rejected by the operator ("not valid"; wants reference-architecture parity). Also relies on an `any(...)` schema escape hatch.
* **Leave the connection manual / live-only (no script).** Rejected: re-introduces a manual `az` step, fails "single `azd up`," and is not reproducible across environments.
* **Literal pre-Phase-4 revert (env → base CognitiveSearch connection).** Rejected: re-opens BUG-0025/0059 (the base connection 401s). This is the trap the synthesis above guards against.

### Scenario 2 — `macae` reference scrub

**Requirements:** zero `macae` in shipped artifacts; preserve technical content + decision traceability; don't self-defeat by scrubbing the policy that authorizes pattern-borrowing.

**Preferred Approach — scrub shipped artifacts + bugs.md attribution; KEEP governance/tracking/sample/ADRs+worklogs (pending operator confirm on ADRs/worklogs):**

* SCRUB (reword to "the read-only reference architecture" / "reference-architecture pattern"): V2-SRC (41), NEW-INFRA comments (main.bicep 7, virtualNetwork.bicep 1, azure.yaml 1), V2-ENV (1), V2-TESTS (10, incl. rename `test_rai_agent_uses_macae_classifier_pattern` → `test_rai_agent_uses_classifier_pattern`), V2-DOCS-BUGS (11 — attribution wording only, keep all technical facts; also fix the stale target api-version).
* For the `Phase: 4 (... MACAE re-skin ...)` header tails, trimming to the standing phase name also satisfies Hard Rule #16 — two-birds (operator decision Q2).
* KEEP (do not scrub): REPO-GOVERNANCE `.github/**` (Hard Rule #9 sanctioned citations — scrubbing these is a policy change), TRACKING `.copilot-tracking/**` (agent process history), SAMPLE-FOLDER `data/sample_code/macae/**` (the actual read-only reference).
* DECISION NEEDED: V2-OTHER `v2/docs/**` ADRs + worklogs (80+). Recommend KEEP (ADRs cite the sanctioned reference like governance; worklogs are dated immutable history per Hard Rule #19). If scrubbed, do it as its own mechanical one-unit pass.

#### Considered Alternatives

* **Full scrub including governance + ADRs + worklogs + tracking.** Rejected as default: scrubbing `.github/**` removes the Hard Rule #9 policy that authorizes the borrowing (a separate policy change needing explicit confirmation); scrubbing dated worklogs/tracking rewrites durable history.
* **Delete the `data/sample_code/macae/**` folder.** Out of scope unless the operator wants the reference removed entirely — but see the security flag (its `.azure/**` logs carry real IDs and should be gitignored/stripped regardless).

## Open Decisions For The Operator

* **D1 — Seeder hook timing:** `postprovision` (connection is infra-adjacent; KB content not required to create the connection) vs `postdeploy` (alongside the existing `upload_sample_data` hook). Recommend `postprovision`.
* **D2 — Scrub breadth:** shipped artifacts + bugs.md only (recommended), or also `v2/docs/**` ADRs + worklogs (separate mechanical pass)?
* **D3 — Header tails:** trim `Phase: 4 (... MACAE re-skin ...)` to the standing phase name (also fixes Hard Rule #16) vs. reword to "reference-architecture re-skin"?
* **D4 — External path references:** also drop the external sample file paths cited next to "MACAE" (`common/utils/utils_af.py`, `components/auth/LoginButton`, `commonComponents/imports/ContosoLogo`, `src/backend/v4/common/services/mcp_service.py`), or keep them?
* **D5 — Security:** verify `data/sample_code/macae/.azure/**` (real subscription GUID + RG name in `provision-preview.log` / `azd-up-3.log`) is gitignored or strip it (Hard Rule #18 / `azure-env-ids` rule). Independent of the scrub.
* **D6 — RBAC/deps:** confirm the deploy identity holds `Azure AI User` on the Foundry account, and that `httpx` + `azure-identity` are in `v2/pyproject.toml` (avoid adding `azure-ai-projects`).
