<!-- markdownlint-disable-file -->
# Subagent research — `macae` reference inventory + KB-MCP Bicep removal plan

Status: Complete
Date: 2026-06-25
Scope: READ-ONLY inventory + removal planning. No files modified except this one.
Workspace root: c:\workstation\Microsoft\github\cwyd-cdb

Two goals:

- GOAL A — complete case-insensitive `macae` inventory across the whole workspace, grouped by file, each match tagged, with a neutral replacement proposed for every non-tracking / non-sample shipped-artifact match.
- GOAL B — concrete removal plan for the Phase-4 KB-MCP Bicep module (`ai-project-kb-mcp-connection.bicep`) and its `main.bicep` wiring.

---

## Executive summary (return-to-user facts)

- Pre-Phase-4 value of `AZURE_AI_SEARCH_CONNECTION_NAME` (CONFIRMED via git diff of the commit that introduced `aiProjectKbMcpConnection`):
  `databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : ''`
  i.e. the revert target is `aiProjectSearchConnection!.outputs.name` (the base CognitiveSearch connection). The base connection module `aiProjectSearchConnection` STAYS.
- `searchKnowledgeBaseApiVersion` does NOT become orphaned after the module is deleted. It is still consumed at:
  - v2/infra/main.bicep L199 (param definition)
  - v2/infra/main.bicep L1876 (backend app setting `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION`)
  - v2/infra/main.bicep L2547 (output `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION`)
  Only the L1074 reference (inside the deleted module call) goes away. No other param/var/output is orphaned by the removal.
- Tests referencing the KB-MCP Bicep module: NONE. A scoped search for `ai-project-kb-mcp` / `aiProjectKbMcpConnection` / `kbMcpConnection` returns matches only in v2/infra/main.bicep, the generated v2/infra/main.json, the module file itself, and .copilot-tracking history docs. No file under v2/tests asserts the module exists, so deletion breaks no test.

### `macae` match totals by classification tag

| Tag | What it covers | Approx count | Scrub? |
| --- | --- | --- | --- |
| V2-SRC (production code) | v2/src/** (backend + frontend) | 41 | YES — reword |
| NEW-INFRA | v2/infra/** + v2/azure.yaml (.bicep / .yaml source) | 11 source lines (+2 in the to-be-deleted module; + generated main.json refs) | YES — reword (kb-mcp file deleted) |
| V2-ENV | v2/.env | 1 | YES — reword (gitignored, but a shipped sample default) |
| V2-TESTS | v2/tests/** | 10 | YES — reword + rename one test |
| V2-DOCS-BUGS | v2/docs/bugs.md | 11 distinct lines | YES — reword proper-noun attribution only; KEEP technical content |
| V2-OTHER (docs) | v2/docs ADRs + worklogs + agents.md | ~80+ (search capped) | DECISION NEEDED (recommend KEEP — see clarifying question) |
| REPO-GOVERNANCE | .github/** (copilot-instructions, cwyd-planner agent, v2-frontend instructions) | 10 | NO — intentional sanctioned citations |
| TRACKING | .copilot-tracking/** | 200+ (search capped) | NO — process history |
| SAMPLE-FOLDER | data/sample_code/macae/** | hundreds (full upstream clone) | NO — read-only reference clone |

Clean-tree confirmations (zero `macae` matches):

- v1 `code/**` — 0
- root `docs/**`, root `infra/**`, root `tests/**`, root `scripts/**`, `extensions/**`, root `README.md` — 0 (MACAE is a v2-era reference; v1 predates it)
- `data/sample_code/macae/` exists and IS the read-only upstream clone (the user-suggested `data/sample_code/macae/**` path is real; an earlier file_search glob missed it, but a `data/**` grep confirms it).

---

## GOAL A — complete `macae` inventory (grouped by file)

Neutral-replacement convention used below (drops the proper noun, preserves meaning):

- "MACAE pattern" -> "the read-only reference architecture pattern" (or "reference-architecture pattern")
- "mirrors MACAE" / "mirroring MACAE" -> "mirrors the reference architecture"
- "MACAE re-skin" -> "reference-architecture re-skin"
- "MACAE-style X" -> "reference-architecture-style X"
- "MACAE adds / MACAE collapses ..." -> "the reference architecture adds / we collapse ..."
- "confirmed against MACAE" -> "confirmed against the reference architecture"
- "MACAE interlocking glyph" -> "the reference architecture's interlocking glyph"
- test `test_rai_agent_uses_macae_classifier_pattern` -> `test_rai_agent_uses_classifier_pattern`

### V2-SRC — production code (v2/src/**) — 41 matches — reword

Backend:

- v2/src/backend/core/agents/definitions.py
  - L23: `var (MACAE adds AZURE_OPENAI_RAI_DEPLOYMENT_NAME; we collapse` -> "var (the reference architecture adds `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`; we collapse"
  - L37: `MACAE pattern attribution: TRUE/FALSE classifier prompt shape used by` -> "Reference-architecture attribution: TRUE/FALSE classifier prompt shape used by"
  - L154: `# MACAE pattern (common/utils/utils_af.py create_RAI_agent): a` -> "# Reference-architecture pattern (a dedicated Foundry agent acting as a TRUE/FALSE classifier...)". NOTE: the original cites an external path `common/utils/utils_af.py` — drop the external path too if a full proper-noun scrub is desired.
- v2/src/backend/core/tools/content_safety.py
  - L21: `classifier misses (MACAE pattern -- common/utils/utils_af.py` -> "classifier misses (reference-architecture pattern; ...)"
  - L22: `create_RAI_agent, adapted; v2 collapses MACAE's per-RAI env var` -> "...adapted; v2 collapses the reference architecture's per-RAI env var"
  - L156: `MACAE attribution: the TRUE/FALSE classifier prompt shape and the` -> "Reference-architecture attribution: the TRUE/FALSE classifier prompt shape and the"
  - L160: `instead of MACAE's per-RAI env var.` -> "instead of the reference architecture's per-RAI env var."

Frontend (theme):

- v2/src/frontend/src/theme/tokens.css L3: `Phase: 4 (frontend polish — MACAE re-skin: tokens.css thinned to a` -> "...reference-architecture re-skin: tokens.css thinned to a"
- v2/src/frontend/src/theme/FluentThemeBridge.tsx
  - L3: `Phase: 4 (frontend polish — MACAE re-skin) +` -> "...reference-architecture re-skin) +"
  - L12: `(teamsLightTheme / teamsDarkTheme, mirroring MACAE).` -> "...mirroring the reference architecture)."

Frontend (chat page):

- v2/src/frontend/src/pages/chat/components/MessageList.tsx L6 — "MACAE re-skin — assistant runs as full-width prose ..." -> "reference-architecture re-skin — ..."
- v2/src/frontend/src/pages/chat/components/MessageList.module.css L4 — "MACAE re-skin — assistant: no bubble ..." -> "reference-architecture re-skin — ..."
- v2/src/frontend/src/pages/chat/components/MessageInput.tsx L4 — "MACAE re-skin — composer pill ..." -> "reference-architecture re-skin — ..."
- v2/src/frontend/src/pages/chat/components/MessageInput.module.css L4 — "MACAE re-skin — composer pill ..." -> "reference-architecture re-skin — ..."
- v2/src/frontend/src/pages/chat/components/HistoryPanel.tsx L24 — "Phase 4 MACAE re-skin: rows render as MACAE-style .tab chips" -> "Phase 4 reference-architecture re-skin: rows render as reference-architecture-style .tab chips"
- v2/src/frontend/src/pages/chat/components/HistoryPanel.module.css L4 — "MACAE re-skin — rows use Fluent tokens ..." -> "reference-architecture re-skin — ..."
- v2/src/frontend/src/pages/chat/ChatPage.tsx
  - L5 — "MACAE re-skin — sidebar moved LEFT ..." -> "reference-architecture re-skin — ..."
  - L12 — "on the LEFT (matching MACAE) + a centered main column ..." -> "on the LEFT (matching the reference architecture) + ..."
- v2/src/frontend/src/pages/chat/ChatPage.module.css L4 — "MACAE re-skin — sidebar moved LEFT)" -> "reference-architecture re-skin — ..."

Frontend (Header components):

- v2/src/frontend/src/components/Header/userIdentity.tsx
  - L9 — "Initials derivation mirrors MACAE's components/auth/LoginButton" -> "Initials derivation mirrors the reference architecture's login-button pattern"
  - L50 — "Up-to-two-letter initials from a display name (mirrors MACAE's ...)" -> "...mirrors the reference architecture's ..."
- v2/src/frontend/src/components/Header/MultiAgentLogo.tsx
  - L3 — "Phase: 4 (frontend polish — MACAE re-skin)" -> "...reference-architecture re-skin)"
  - L6 — "interlocking glyph the MACAE multi-agent experience renders for its" -> "interlocking glyph the reference architecture's multi-agent experience renders for its"
  - L7 — "brand badge (adapted from MACAE's ...)" -> "brand badge (adapted from the reference architecture's ...)"
- v2/src/frontend/src/components/Header/MsftColorLogo.tsx
  - L3 — "Phase: 4 (frontend polish — MACAE re-skin)" -> "...reference-architecture re-skin)"
  - L6 — "MACAE's commonComponents/.../MsftColor. Used as the" -> "the reference architecture's color-logo component. Used as the"
- v2/src/frontend/src/components/Header/HeaderTools.tsx
  - L3 — "Phase: 4 (frontend polish — MACAE re-skin)" -> "...reference-architecture re-skin)"
  - L15 — "(mirrors MACAE's HeaderTools): the toggle button ..." -> "(mirrors the reference architecture's header tools): ..."
- v2/src/frontend/src/components/Header/Header.tsx
  - L3 — "Phase: 4 (frontend polish — MACAE re-skin)" -> "...reference-architecture re-skin)"
  - L5 — "Coral Header. Mirrors MACAE's ..." -> "Coral Header. Mirrors the reference architecture's ..."
- v2/src/frontend/src/components/Header/Header.module.css
  - L2 — "Phase: 4 (frontend polish — MACAE re-skin)" -> "...reference-architecture re-skin)"
  - L4 — "Header CSS Module. Mirrors MACAE's ..." -> "Header CSS Module. Mirrors the reference architecture's ..."

Frontend (CoralShell components):

- v2/src/frontend/src/components/CoralShell/PanelLeft.tsx L3 (Phase header), L5 ("Mirrors MACAE's ...") -> reference-architecture wording
- v2/src/frontend/src/components/CoralShell/CoralShellRow.tsx L3, L5 -> reference-architecture wording
- v2/src/frontend/src/components/CoralShell/CoralShellColumn.tsx L3, L5 -> reference-architecture wording
- v2/src/frontend/src/components/CoralShell/CoralShell.module.css L2, L4 -> reference-architecture wording

NOTE (Hard Rule #16 interaction): several of these are `Phase: 4 (... MACAE re-skin ...)` docstring/comment headers. Hard Rule #16 already forbids process narrative in `Phase:` header tails; the cleanest scrub for those is to reduce the tail to the standing phase name only (e.g. `Phase: 4 (frontend polish)`), which removes the proper noun AND the process-narrative tail in one edit. Decide per the user's preference (full neutral reword vs. tail trim).

### NEW-INFRA — v2/infra/** + v2/azure.yaml — reword

- v2/infra/main.bicep (7 matches; all are comments)
  - L289: `// Reference: Multi-Agent Custom Automation Engine (MACAE) sample` -> "// Reference: the read-only reference architecture sample"
  - L1596: `// matching the MACAE mixed-hosting pattern.` -> "// matching the reference-architecture mixed-hosting pattern."
  - L1776: `// (MACAE managed-identity pull pattern). server is the same` -> "// (reference-architecture managed-identity pull pattern). ..."
  - L1949: `//   - Mixed hosting (ACA backend + App Service frontend) follows MACAE's` -> "// ... follows the reference architecture's"
  - L2014: `// Build-from-source App Service (MACAE pattern, BUG-0081 fix). azd` -> "// Build-from-source App Service (reference-architecture pattern, BUG-0081 fix). ..."
  - L2031: `// at runtime (MACAE pattern). No build-time bake — the Vite` -> "// at runtime (reference-architecture pattern). ..."
  - L2252: `// requires min 3. solutionSuffix is generated by MACAE pattern as 8+` -> "// ... generated by the reference-architecture pattern as 8+"
- v2/infra/modules/virtualNetwork.bicep
  - L27: `//   MACAE pattern (read-only):    Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/infra/main.bicep` -> "// reference architecture pattern (read-only): infra/main.bicep" (drop the named repo path)
- v2/azure.yaml
  - L118: `# Build-from-source on App Service (MACAE pattern). host: appservice` -> "# Build-from-source on App Service (reference-architecture pattern). host: appservice"
- v2/infra/modules/ai-project-kb-mcp-connection.bicep (2 matches — MOOT, file is DELETED per Goal B)
  - L3: `// Phase:   4 (MACAE infra parity)`
  - L46: `// are not in the typed Bicep schema (mirrors the MACAE reusable`
- v2/infra/main.json (generated ARM) — carries the compiled `aiProjectKbMcpConnection` references (L22832, L22836, L48460, L49995). This file is a build artifact; it is regenerated from main.bicep by `az bicep build` / azd, so it is fixed by the Goal-B edit + rebuild, not hand-edited.

### V2-ENV — v2/.env — reword

- v2/.env L50: `# Created live as cwyd-kb-mcp per MACAE's seed_kb_connections.py payload`
  -> `# Created live as cwyd-kb-mcp per the reference architecture's KB-connection seed payload`
  (Gitignored file, but it ships as the local-dev sample; reword to drop the proper noun + external script name.)

### V2-TESTS — v2/tests/** — 10 matches — reword + rename one test

- v2/tests/backend/core/agents/test_definitions.py
  - L10 (module docstring): `* RAI_AGENT.instructions follows the MACAE TRUE/FALSE classifier` -> "... follows the reference-architecture TRUE/FALSE classifier"
  - L260: `def test_rai_agent_uses_macae_classifier_pattern() -> None:` -> RENAME to `def test_rai_agent_uses_classifier_pattern() -> None:`
  - L261 (test docstring): `"""The MACAE-style RAI classifier returns exactly one token` -> "The reference-architecture-style RAI classifier returns exactly one token"
- v2/tests/frontend/theme/FluentThemeBridge.test.tsx L3 — Phase header "MACAE re-skin" -> "reference-architecture re-skin"
- v2/tests/frontend/components/PanelLeft.test.tsx L3 — Phase header -> reference-architecture wording
- v2/tests/frontend/components/MultiAgentLogo.test.tsx L3 — Phase header -> reference-architecture wording
- v2/tests/frontend/components/Header.test.tsx
  - L3 — Phase header -> reference-architecture wording
  - L8 — "but the brand visuals are now MACAE-faithful: Microsoft 4-square" -> "...now reference-architecture-faithful: ..."
  - L49 — "// Default subtitle from MACAE pattern: \"<title> | Solution Accelerator\"." -> "// Default subtitle from the reference-architecture pattern: ..."
- v2/tests/frontend/components/CoralShell.test.tsx L3 — Phase header -> reference-architecture wording

RENAME CAUTION (Hard Rule #11 naming stability): `test_rai_agent_uses_macae_classifier_pattern` is a test function name, not a shipped public API, so renaming it is low-risk. The only other reference to that token is .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md L8 (a tracking doc — not updated). The stale `.pytest_cache/v/cache/nodeids` entry (gitignored cache) regenerates on the next test run.

### V2-DOCS-BUGS — v2/docs/bugs.md — 11 distinct lines — reword attribution ONLY (KEEP technical content)

Per the user instruction: do NOT delete the technical content of bugs.md; only reword the proper-noun attribution. Lines: 83, 105, 130 (two occurrences), 131, 411, 508 (two), 521 (two), 523 (three), 851, 1222 (three), 1237 (three).

Representative rewordings (apply the same convention to each occurrence):

- L83 — "Root cause (confirmed against MACAE): the tool pointed at the wrong connection category ..." -> "Root cause (confirmed against the read-only reference architecture): ..." (keep the entire `RemoteTool` / `ProjectManagedIdentity` / `audience` technical detail).
- L105 / L851 — "port the v1 getUserInfo() flow + the MACAE header-forward pattern" -> "...+ the reference architecture's header-forward pattern".
- L130 / L1222 — "removed the name prop from <Avatar> (mirrors MACAE ...)" and "the MACAE interlocking glyph adapted from MACAE's commonComponents/imports/ContosoLogo" -> "...(mirrors the reference architecture ...)" and "...adapted from the reference architecture's logo component".
- L131 / L1237 — "userInitials mirrors MACAE's getUserInitials" and "Reviewed MACAE's components/auth/LoginButton" -> "...mirrors the reference architecture's initials helper" / "Reviewed the reference architecture's login-button pattern".
- L411 — "Cross-checked against MACAE, whose one bearer-attached MCP client path sets headers[\"Authorization\"] ... (src/backend/v4/common/services/mcp_service.py)" -> "Cross-checked against the reference architecture, whose ... MCP client path sets ...". Drop the external file path if a full scrub is desired.
- L508 / L521 / L523 — the BUG-0025 root-cause narrative ("confirmed against MACAE", "MACAE creates one connection per KB at post-deploy (infra/scripts/seed_kb_connections.py)", "using MACAE's payload", "matching MACAE", "unlike MACAE's dynamic content-pack KBs") -> replace each "MACAE" with "the reference architecture" and keep every technical fact (connection category, payload fields, role grants, audience).

### V2-OTHER — v2/docs ADRs + worklogs + agents.md — ~80+ matches (search capped) — DECISION NEEDED

These are documentation, not shipped runtime artifacts. Two sub-kinds:

- ADRs (architectural decision records) that cite the reference architecture as the basis of a decision:
  - v2/docs/agents.md (L22, L119)
  - v2/docs/adr/0008-lazy-foundry-agent-bootstrap.md (L18, L22 ×2, L33)
  - v2/docs/adr/0015-frontend-path-alias-cross-folder-imports.md (L18 ×2, L113 ×2, L123, L130, L147)
  - v2/docs/adr/0016-agent-framework-foundry-iq-tas27-parity-review.md (L12, L33, L59, L137)
  - v2/docs/adr/0021-agent-framework-foundry-iq-kb-default.md (L27, L35, L51 ×2, L53)
  - v2/docs/adr/0025-foundry-prompt-agent-ga-pattern.md (L23, L35, L53)
  - v2/docs/adr/0028-event-grid-single-trigger-blob-ingestion.md (L19, L54 ×2)
- Worklogs (dated daily process history):
  - v2/docs/worklog/2026-06-11.md (L41, L79)
  - v2/docs/worklog/2026-06-12.md (many: L13, L17, L27, L41, L47 ×2, L82, L89, L91 ×2, L93, L101 ×4, L107, L108 ×2, L120, L126, L131, L188, L190 ×3, L192 ×3, L193, L194 ×2, L196, L198 ×2, L202, L208, L210, L212)
  - v2/docs/worklog/2026-06-14.md (L199)
  - v2/docs/worklog/2026-06-15.md (L320, L710, L714, L758)
  - v2/docs/worklog/2026-06-20.md (L3, L13, L19, L20, L90 ×2)
  - v2/docs/worklog/2026-06-22.md (L18 ×2, L38 ×2)

Recommendation: KEEP as-is (do not scrub). Rationale: (a) ADRs legitimately name the reference architecture as the sanctioned read-only source under Hard Rule #9 — same justification as the REPO-GOVERNANCE citations; renaming the proper noun in a decision record erases the traceable basis of the decision. (b) Worklogs are dated, immutable process history (the Hard Rule #19 durable record) — equivalent in spirit to .copilot-tracking, which the task already exempts. Scrubbing dated history rewrites the record. If the user nevertheless wants ADRs/worklogs scrubbed, apply the same "the reference architecture" reword convention; this is a large but mechanical edit (~80+ occurrences across ~13 files) and should be its own one-unit pass, not folded into the shipped-artifact scrub. See clarifying question Q1.

### REPO-GOVERNANCE — .github/** — 10 matches — KEEP (intentional)

- .github/copilot-instructions.md L23 (sanctioned read-only source URL), L27 (pattern attribution), L46 (Hard Rule #9 "CGSA/MACAE are read-only architectural references").
- .github/agents/cwyd-planner.agent.md L2 (×2 in the description), L24 (reference URL), L53 (citation template), L83 ("Cite, don't copy ... MACAE/CGSA"), L93 ("Borrow patterns from MACAE/CGSA ... with a citation").
- .github/instructions/v2-frontend.instructions.md L11 ("The MACAE re-skin (dev_plan task #34) committed the decision ...").

These are governance / agent-instruction citations of the sanctioned reference. They are the policy that authorizes the very pattern-borrowing being scrubbed elsewhere; they must stay. (If the user wants even governance scrubbed, that is a separate policy change to Hard Rule #9 and requires explicit confirmation — out of scope for an artifact scrub.)

### TRACKING — .copilot-tracking/** — 200+ matches (search capped) — KEEP

Process history from the `macae-infra-parity` work and prior research. Representative files (not exhaustive):

- .copilot-tracking/changes/2026-06-25/macae-infra-parity-changes.md
- .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md
- .copilot-tracking/plans/2026-06-25/macae-infra-parity-plan.instructions.md
- .copilot-tracking/plans/logs/2026-06-25/macae-infra-parity-log.md
- .copilot-tracking/research/2026-06-25/macae-infra-parity-research.md
- .copilot-tracking/research/2026-06-25/wi-01-kb-mcp-connection-schema.md
- .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md
- .copilot-tracking/research/subagents/2026-06-25/macae-identity-env-hooks.md
- .copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md
- .copilot-tracking/research/subagents/2026-06-25/macae-kb-mcp-postdeploy-pattern.md
- .copilot-tracking/research/subagents/2026-06-25/v2-frontend-appservice-scope.md
- .copilot-tracking/research/subagents/2026-06-24/manual-change-debt-deployment-iac.md
- (several file/dir NAMES themselves contain `macae`)

Not scrubbed. This is the agent's own working history.

### SAMPLE-FOLDER — data/sample_code/macae/** — hundreds of matches — KEEP

This is a full read-only clone of the Multi-Agent Custom Automation Engine Solution Accelerator (azure.yaml, azure_custom.yaml, infra/**, src/**, docs/**, content packs, post-provision scripts, and `.azure/` logs). It is the read-only reference; do not scrub.

SECURITY OBSERVATION (flag to user, do not reproduce values): the sample's `.azure/` logs carry REAL environment identifiers from whoever ran the upstream sample — e.g. data/sample_code/macae/.azure/provision-preview.log and data/sample_code/macae/.azure/azd-up-3.log embed a real subscription GUID, a real resource-group name, and portal deep-links. Per the user's azure-env-ids rule and Hard Rule #18, those real IDs should not propagate into any tracked CWYD artifact. If `data/sample_code/macae/.azure/**` is actually tracked (not gitignored), recommend the user verify it is ignored or strip those logs. (This research file intentionally uses placeholders such as <AZURE_SUBSCRIPTION_ID> / <RESOURCE_GROUP> and does NOT copy the literal values.)

---

## GOAL B — KB-MCP Bicep removal plan

Source of the directive: the operator rejected the durable Bicep approach for the `cwyd-kb-mcp` Foundry Project RemoteTool connection (added in "Phase 4"). See .copilot-tracking/research/2026-06-25/remove-kb-mcp-bicep-and-macae-scrub-research.md.

### B.1 — Delete the module file

- DELETE the entire file: v2/infra/modules/ai-project-kb-mcp-connection.bicep
  (declares `param aiServicesAccountName`, `param projectName`, `param searchEndpoint`, `param knowledgeBaseName='cwyd-kb'`, `param knowledgeBaseApiVersion='2025-11-01-preview'`, `param connectionName='${knowledgeBaseName}-mcp'`, resource `kbMcpConnection` (`RemoteTool` / `ProjectManagedIdentity` / `audience` via `any(...)`), and outputs `name` / `resourceId`). All of these live inside the file and vanish with it; none are referenced elsewhere except via the module call removed in B.2.

### B.2 — Delete the module instantiation + its leading comment in main.bicep

- DELETE v2/infra/main.bicep lines 1061-1076 inclusive:
  - L1061-1066 — the leading comment block:
    ```
    // Foundry Project RemoteTool connection for the KB MCP path (cosmosdb mode
    // only). This is what AZURE_AI_SEARCH_CONNECTION_NAME must resolve to: the
    // CognitiveSearch connection above 401s on the /knowledgebases/.../mcp path
    // (BUG-0025 / BUG-0059). Authenticates as the Project system identity
    // (ProjectManagedIdentity + search.azure.com audience); the Project MI holds
    // Search Service Contributor on the Search service.
    ```
  - L1067-1076 — the module block:
    ```
    module aiProjectKbMcpConnection 'modules/ai-project-kb-mcp-connection.bicep' = if (databaseType == 'cosmosdb') {
      name: take('module.ai-project-kb-mcp-connection.${solutionSuffix}', 64)
      params: {
        aiServicesAccountName: aiServicesName
        projectName: aiProject.outputs.name
        searchEndpoint: effectiveSearchEndpoint
        knowledgeBaseName: searchKnowledgeBaseName
        knowledgeBaseApiVersion: searchKnowledgeBaseApiVersion
      }
    }
    ```
- KEEP v2/infra/main.bicep lines 1048-1059 unchanged — the base CognitiveSearch connection module `aiProjectSearchConnection` (this is the revert target for the env var). Its leading comment (L1048-1050) stays.

### B.3 — Revert `AZURE_AI_SEARCH_CONNECTION_NAME` to the base connection

- v2/infra/main.bicep L1881, change FROM:
  ```
  { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectKbMcpConnection!.outputs.name : '' }
  ```
  TO (the CONFIRMED pre-Phase-4 value):
  ```
  { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : '' }
  ```
- The preceding comment block (L1872-1880) already describes this env as resolving to the "category CognitiveSearch" Project↔Search connection and being passed as the KB MCP tool's `project_connection_id`. After the revert the comment is consistent again (it described the base CognitiveSearch connection all along), so no comment change is strictly required. If the operator wants the comment to reflect that the base connection is the (known-401-ing per BUG-0025) path, that is an optional editorial note — but the directive is just to revert the value.

Git confirmation (read-only):
```
git -C <repo> log -p -S "aiProjectKbMcpConnection" -- v2/infra/main.bicep
```
shows exactly this hunk for the introducing commit:
```
-            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : '' }
+            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectKbMcpConnection!.outputs.name : '' }
```
=> the revert restores `aiProjectSearchConnection!.outputs.name`.

### B.4 — Orphaned params / vars / outputs check (result: none)

- `searchKnowledgeBaseApiVersion` — NOT orphaned. Still used at main.bicep L199 (param), L1876 (app setting), L2547 (output). Only the L1074 reference (inside the deleted module call) is removed. KEEP the param.
- `searchKnowledgeBaseName` — NOT orphaned. Still used at main.bicep L1873 (app setting `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME`) and the `aiProjectSearchConnection` module call (L1057) + output (~L2541). KEEP.
- `effectiveSearchEndpoint` — NOT orphaned. Still used at L1869 (`AZURE_AI_SEARCH_ENDPOINT`). KEEP.
- `aiServicesName`, `aiProject.outputs.name` — used pervasively. KEEP.
- Net: removing the module + its call orphans NOTHING. No param/var/output needs deletion.

### B.5 — Generated ARM (main.json) + tests

- v2/infra/main.json (the compiled ARM template) contains the `aiProjectKbMcpConnection` deployment object (L22832, L22836), the `AZURE_AI_SEARCH_CONNECTION_NAME` reference to `aiProjectKbMcpConnection` (L48460), and the module dependency entry (L49995). main.json is a build artifact; after the main.bicep edit it must be regenerated (`az bicep build` / azd `provision` rebuild) rather than hand-edited. The regenerated main.json will reference `aiProjectSearchConnection` again and drop the kb-mcp module.
- Tests asserting the KB-MCP Bicep module exists: NONE. Scoped search (`ai-project-kb-mcp` / `aiProjectKbMcpConnection` / `kbMcpConnection`) returns only: main.bicep (L1067, L1068, L1881), main.json (generated), the module file itself, and .copilot-tracking docs. No v2/tests reference. Deletion breaks no test.

### B.6 — Post-edit validation (read-only checklist for the implementer)

- `az bicep build --file v2/infra/main.bicep` must succeed with the module removed and main.json regenerated clean.
- Grep that `aiProjectKbMcpConnection` and `ai-project-kb-mcp-connection` no longer appear in v2/infra/main.bicep (only the regenerated main.json should be free of them too after rebuild).
- Confirm `AZURE_AI_SEARCH_CONNECTION_NAME` now resolves to `aiProjectSearchConnection!.outputs.name`.

---

## Evidence index (read-only commands / reads used)

- git: `git -C <repo> log -p -S "aiProjectKbMcpConnection" -- v2/infra/main.bicep | Select-String AZURE_AI_SEARCH_CONNECTION_NAME -Context 1,1` -> confirmed pre-Phase-4 value `aiProjectSearchConnection!.outputs.name`.
- read: v2/infra/main.bicep L1030-1095 (module region), L1855-1895 (env region) -> module block L1061-1076, env L1881.
- read: v2/infra/modules/ai-project-kb-mcp-connection.bicep L1-80 (full module).
- read: v2/src/backend/core/agents/definitions.py L15-45, L150-170; v2/src/backend/core/tools/content_safety.py L15-30, L150-165 -> production-code wording.
- read: v2/tests/backend/core/agents/test_definitions.py L250-300 -> test name + docstring.
- grep (scoped): `**/*.bicep`, `.github/**`, `v2/src/**`, `v2/docs/**`, `v2/docs/bugs.md`, `v2/tests/**`, `v2/infra/main.bicep`, `v2/azure.yaml`, `v2/infra/modules/virtualNetwork.bicep`, `v2/.env`, `.copilot-tracking/**`, `code/**`, `data/**`, `docs/**`, `infra/**`, `searchKnowledgeBaseApiVersion`, `ai-project-kb-mcp|aiProjectKbMcpConnection|kbMcpConnection`, `macae_classifier`.

NOTE on search completeness: a single unscoped `macae` grep over `v2/**` with ignored files included TIMES OUT; the inventory above was assembled from scoped per-area greps. The `v2/docs/**` and `.copilot-tracking/**` sweeps were capped (80 / 200) with "more available", so V2-OTHER and TRACKING counts are lower bounds (file-level classification is complete; line-level enumeration for those two KEEP buckets is intentionally partial per the Researcher-Subagent "no exhaustive investigation beyond scope" rule).

---

## Recommended next research (not done this session)

- [ ] If the user decides to scrub V2-OTHER docs (ADRs + worklogs), do a full line-level enumeration of v2/docs/** (the search was capped at 80) before editing.
- [ ] If a full proper-noun scrub is wanted, decide policy on the embedded EXTERNAL file paths that accompany "MACAE" (e.g. `common/utils/utils_af.py`, `components/auth/LoginButton`, `src/backend/v4/common/services/mcp_service.py`, `commonComponents/imports/ContosoLogo`) — these also leak the external sample's structure even after the proper noun is removed.
- [ ] Verify whether data/sample_code/macae/.azure/** (which carries real subscription/RG identifiers) is gitignored; if tracked, recommend removal/strip (Hard Rule #18 / azure-env-ids rule).
- [ ] Confirm the Goal-B edit also wants the optional comment refresh at main.bicep L1872-1880 (describe the base CognitiveSearch connection's known KB-MCP-401 limitation) vs. a value-only revert.

## Clarifying questions

- Q1 — Scope of the scrub: should V2-OTHER docs (ADRs + worklogs in v2/docs/**) be scrubbed too, or only the shipped runtime artifacts (V2-SRC, NEW-INFRA, V2-ENV, V2-TESTS) plus bugs.md attribution? Recommendation: KEEP ADRs/worklogs (they cite the sanctioned reference the same way governance does, and worklogs are dated history). REPO-GOVERNANCE and TRACKING and SAMPLE-FOLDER stay regardless.
- Q2 — For the `Phase: 4 (... MACAE re-skin ...)` header comments in V2-SRC/V2-TESTS: trim the tail to the standing phase name only (also satisfies Hard Rule #16), or keep a descriptive tail with "reference-architecture re-skin"?
- Q3 — Full scrub vs. proper-noun-only: also drop the accompanying EXTERNAL sample file paths cited next to "MACAE", or leave those technical path references intact?
