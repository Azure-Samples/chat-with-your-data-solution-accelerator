<!-- markdownlint-disable-file -->
# Implementation Quality Validation — BUG-0054 Phase 2

**Scope:** full-quality. **Date:** 2026-06-29.
**Note:** The `Implementation Validator` subagent was provisioned with read-only session-store access only and reported Blocked (could not read the changed files). These findings were produced by the reviewer via direct file reads + test execution.

**Changed files:**
- `v2/infra/main.bicep` (role-assignment idempotency hardening)
- `v2/tests/infra/test_main_bicep.py` (regression assertions)

## Severity counts: 0 Critical, 0 Major, 3 Minor

## 1. Bicep correctness — PASS

- `searchOpenAiUserOnFoundry` (main.bicep:1038) — `name: guid(aiServicesAccount.id, 'srch-${solutionSuffix}', subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-...'))`, `scope: aiServicesAccount`. The `aiServicesAccount` `existing` resource (main.bicep:1034) is guarded by the **same** condition `if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi)` as the assignment → `.id` always resolves when the assignment deploys. No unresolved-reference / BCP318 risk.
- `searchOpenAiUserOnReusedOpenAi` (main.bicep:1050) — `name: guid(existingOpenAi.id, 'srch-${solutionSuffix}', subscriptionResourceId(...))`, `scope: existingOpenAi`. The assignment condition requires `useExistingOpenAi == true`; `existingOpenAi` is declared under `if (useExistingOpenAi)` → resolves. No risk.
- `az bicep build` EXIT=0, no BCP120 (confirmed independently this session).

## 2. Idempotency objective — PASS

- For a fixed `(scope, suffix, roleDef)` the `guid()` output is byte-stable across provisions → the cross-run rename that produced orphan `<ORPHAN_ROLE_ASSIGNMENT_GUID>` is eliminated.
- The deploy-time `systemAssignedMIPrincipalId` is deliberately kept out of the `name` (BCP120) and correctly bound via `properties.principalId` (main.bicep:1043, 1055). Sound.
- The `'srch-${solutionSuffix}'` salt is start-time-knowable and unique across the two assignments because the **scope id differs** (`aiServicesAccount.id` vs `existingOpenAi.id`); the salt only needs to disambiguate within a scope. Collision-safe.

## 3. Naming-convention drift (Hard Rule #11) — PASS

- Only the `name:` `guid()` arguments changed. Resource symbol names (`searchOpenAiUserOnFoundry`, `searchOpenAiUserOnReusedOpenAi`), `scope:`, `roleDefinitionId:`, and `principalId:` are untouched. No shipped-symbol rename.

## 4. Test quality — PASS

- `test_search_openai_role_assignments_use_idempotent_name` (test L671) uses **exact full-expression positive pins** for both names plus a **negative pin** (`'search-system-mi' not in bicep_text`). Catches a static-salt reversion in both directions; not brittle to benign formatting (asserts the canonical single-line form the file uses).
- EG queue invariant: `bicep_text.count("queueName: blobEventsQueueName") == 2` (test L233) catches any repoint to `doc-processing`.
- No redundant/duplicate assertions. 36/36 suite green (0.06s).

## 5. Literal hoisting (v2-infra "hoist literals repeated 2+×") — MINOR (M-3, pre-existing)

- The role-def GUID `5e0bd9bd-...` appears multiple times across `name:` + `roleDefinitionId:` in these and the precedent `existingOpenAiUamiRole` block. The test extracts it to `_COGNITIVE_SERVICES_OPENAI_USER_ROLE_ID`, but `main.bicep` does not hoist it to a `var`. **Pre-existing** repetition (the precedent block at L699-708 already inlines it); this change did not worsen it (the old `name` already carried the bare literal). Not in Phase 2 scope — flag only; do not action inline (Hard Rule #12, no mid-phase back-fill).

## 6. Security / least-privilege — PASS

- Role unchanged (Cognitive Services OpenAI User), scope unchanged (the OpenAI/Foundry account), principal unchanged (Search system MI). No broadening.

## Minor findings carried from RPI Validator

- **M-1:** `v2/infra/main.json` (git-tracked, pre-compiled ARM) was not regenerated and still contains `'search-system-mi'` (main.json:571, 586). No runtime impact — `azure.yaml` uses `provider: bicep` / `module: main`, so `azd` compiles `main.bicep` directly. Repo-hygiene follow-up, out of Phase 2 scope.
- **M-2 (cosmetic):** `existingOpenAi.id` (L1051) vs `existingOpenAi!.id` (L702) — same conditional symbol, both compile clean; purely stylistic null-assertion inconsistency.

## Overall quality verdict

**PASS.** Minimal, targeted, correct hardening. Deterministic + collision-safe + re-run-stable names, sound principal binding, robust bidirectional test coverage, no naming drift, no scope broadening. Three Minor items, all out-of-scope follow-ups (none block).
