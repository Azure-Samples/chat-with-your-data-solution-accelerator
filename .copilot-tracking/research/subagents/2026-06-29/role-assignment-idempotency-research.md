# Research: Role Assignment Idempotency Defect (RoleAssignmentExists)

Status: Complete

## Research questions

1. Enumerate every `Microsoft.Authorization/roleAssignments` declaration across `v2/infra/**`.
2. Identify the non-idempotent declaration causing `RoleAssignmentExists`.
3. Identify the specific role/principal/scope of the conflicting assignment (orphan GUID `70d96d3a-34c9-4887-8eb2-04191fdec8b1`).
4. Check git history for recently added/changed role assignments under `v2/infra`.
5. Determine the recommended fix + exact Bicep edit + operator unblock command.

## TL;DR

- `azd provision` failed (exit 1) after all 17 resources provisioned, on the **AVM Search Service nested deployment** `avm.res.search.search-service.<SUFFIX>` with `RoleAssignmentExists`, existing-id `70d96d3a34c948878eb204191fdec8b1`.
- The `roleAssignments` array passed to the `aiSearch` module (`v2/infra/main.bicep` lines 922-953) is the declaration that emitted the conflicting PUT. The AVM module names each grant `guid(searchService.id, principalId, roleDefinitionId)`.
- The current template is **internally idempotent** — all five current search-scope tuples have distinct `(principal, role)` pairs and each is granted exactly once (the inline `existingSearch*` blocks are gated to `useExistingSearch`, which is `false` this run). The conflict is **cross-run stale state**: an orphaned grant on the search service from a prior deployment (different AVM version / divergent name formula) whose `(principal, role, scope)` tuple matches a current AVM grant under a *different* assignment name.
- Forensics confirmed the AI Services account and search service were rolled back; the orphan id is no longer resolvable at any scope → a **plain re-run of `azd provision` is the primary unblock**.
- A genuinely non-idempotent-by-construction declaration also exists and should be hardened: `searchOpenAiUserOnFoundry` / `searchOpenAiUserOnReusedOpenAi` (lines 1038, 1050) use a **static salt** `'search-system-mi'` in their name instead of the real principalId.

## Findings

### Q1 — Inventory of `Microsoft.Authorization/roleAssignments` declarations under `v2/infra/**`

Two files declare role assignments: `v2/infra/main.bicep` and `v2/infra/modules/ai-project.bicep`.

Search-scope grants (the failing scope) — all in `v2/infra/main.bicep`:

| Decl / call site | Line | Active this run? | Name expression | Role (built-in) | Principal source | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| `aiSearch` module `roleAssignments[0]` | 922-953 | YES (`cosmosdb && !useExistingSearch`) | AVM internal: `guid(searchService.id, principalId, roleDefId)` | Search Index Data Contributor `8ebe5a00-799e-43f5-93ac-243d3dce84a7` | UAMI principalId | search service |
| `aiSearch` module `roleAssignments[1]` | 922-953 | YES | AVM internal | Search Service Contributor `7ca78c08-252a-4471-8644-bb5ff32d4ba0` | UAMI principalId | search service |
| `aiSearch` module `roleAssignments[2]` | 922-953 | YES | AVM internal | Search Index Data Reader `1407120a-92aa-4202-b7e9-c0e197c71c8f` | `aiProject` projectPrincipalId | search service |
| `aiSearch` module `roleAssignments[3]` | 922-953 | YES | AVM internal | Search Service Contributor `7ca78c08-252a-4471-8644-bb5ff32d4ba0` | `aiProject` projectPrincipalId | search service |
| `aiSearch` module `roleAssignments[4]` | 922-953 | YES | AVM internal | Search Index Data Reader `1407120a-92aa-4202-b7e9-c0e197c71c8f` | deployer (`deployer().objectId`, L258) | search service |
| `existingSearchUamiIndexContributor` | 992 | NO (`useExistingSearch`) | `guid(existingSearch.id, userAssignedIdentity.name, '8ebe5a00-…')` | Search Index Data Contributor | UAMI principalId | existing search |
| `existingSearchUamiServiceContributor` | 1002 | NO | `guid(existingSearch.id, userAssignedIdentity.name, '7ca78c08-…')` | Search Service Contributor | UAMI principalId | existing search |
| `existingSearchProjectIndexReader` | 1012 | NO | `guid(existingSearch.id, aiProject.name, '1407120a-…')` | Search Index Data Reader | project principalId | existing search |

AI-Services-account-scope grants (the search system MI's OpenAI access — NOT the failing scope, but non-idempotent by construction):

| Decl | Line | Active this run? | Name expression | Role | Principal | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| `searchOpenAiUserOnFoundry` | 1038 | YES (`cosmosdb && !useExistingSearch && !useExistingOpenAi`) | `guid(aiServicesName, 'search-system-mi', '5e0bd9bd-…')` — **static salt** | Cognitive Services OpenAI User `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | `aiSearch` systemAssignedMIPrincipalId | AI Services account |
| `searchOpenAiUserOnReusedOpenAi` | 1050 | NO (`useExistingOpenAi`) | `guid(existingOpenAiName, 'search-system-mi', '5e0bd9bd-…')` — **static salt** | Cognitive Services OpenAI User | `aiSearch` systemAssignedMIPrincipalId | reused OpenAI account |

Other `roleAssignments` arrays / resources in `v2/infra/main.bicep` (not search-scope, listed for completeness): lines 344, 593, 699 (`existingOpenAiUamiRole`), 784, 859, 1156, 1314/1325/1336 (`existingStorage*`), 1400 (`sqlRoleAssignments`), 1762, 2327 (`flexDeploymentRole`), 2376 (`eventGridQueueSenderRole`). Plus `v2/infra/modules/ai-project.bicep` line 65 (`projectAiUserRole`, unconditional). None of these is at the search-service scope that threw the error.

### Q2 / Q3 — The declaration that threw the error, and the conflicting tuple

The failed top-level operation targets `Microsoft.Resources/deployments/avm.res.search.search-service.<SUFFIX>` with `state=Failed`, `code=Conflict`, message `DeploymentFailed` → detail `RoleAssignmentExists` → "The role assignment already exists. The ID of the existing role assignment is 70d96d3a34c948878eb204191fdec8b1."

Operation enumeration of that nested deployment (`az deployment operation group list --name avm.res.search.search-service.<SUFFIX> -g <RESOURCE_GROUP>`) returned 10 ops, all `Succeeded`: 1 diagnosticSettings, 3 searchServices, 5 `Microsoft.Authorization/roleAssignments` (names `59cd631c`, `2b069a0f`, `dc5e220f`, `45f6571e`, `7c263c6c` — all "Created"), 1 empty. The orphan `70d96d3a` is **not** any of those five.

The current template grants exactly five search-scope tuples, all with distinct `(principal, role)` pairs:

- `(UAMI, Search Index Data Contributor)`
- `(UAMI, Search Service Contributor)`
- `(Project, Search Index Data Reader)`
- `(Project, Search Service Contributor)`
- `(Deployer, Search Index Data Reader)`

No two are identical, so a single clean run cannot self-collide. Therefore `70d96d3a` is a **sixth assignment name not present in the current template** — a stale orphan from a prior deployment whose name formula differed for one of these same tuples (older AVM module version, the `existingSearch*` NAME-salt path, or a changed `guid()` input). When the current AVM run re-creates that tuple under its own deterministic name, the RBAC backend rejects it because the tuple already exists under `70d96d3a` → `RoleAssignmentExists`.

The exact tuple behind `70d96d3a` could **not** be pinned, and is effectively unpinnable: the AI Services account `aisa-<SUFFIX>` now returns 0 role assignments and `70d96d3a` is not resolvable at the subscription, search-service, or AI-account scope — the search service (and the orphan it carried) was rolled back/removed after the failed run. This matches the user's "if found" qualifier.

Secondary (latent, not this error): `searchOpenAiUserOnFoundry` (L1038) and `searchOpenAiUserOnReusedOpenAi` (L1050) are non-idempotent *by construction* — their names use a static salt `'search-system-mi'` instead of the real principalId. If the search service's system-assigned MI is ever recreated (new principalId), the same assignment name is reused for a different principal, producing `RoleAssignmentExists` / immutable-property-update errors. These are AI-account-scoped, so they did not cause the search-module failure, but they are the most clearly broken idempotency pattern in the file.

### Q4 — Git history (search-RBAC churn)

The search-RBAC surface was actively churned across multiple deployments to the same resource group, which is exactly the condition that produces cross-run orphans:

- `d6b3bdf0` "Feature/fr cwyd 2026 apr (#2234)" — introduced the `avm/res/search/search-service` module.
- `a598c761` "Use chat model for KB seed; add RBAC & docs" — introduced the static-salt `searchOpenAiUserOnFoundry` / `…OnReusedOpenAi` grants (`'search-system-mi'`).
- `f6d73556` "Harden azd deploy: search region and auth fixes" — introduced the **deployer** Search Index Data Reader entry (`aiSearch` array entry 5) and search-region/auth changes.

Any AVM-version bump or change to a `guid()` input between two deployments into the same RG renames the affected assignment while leaving the prior name orphaned — the mechanism observed here.

### Q5 — Recommended fix + exact Bicep + operator unblock

**Primary remedy (no code change): re-run `azd provision`.** The search service and AI Services account were rolled back, so the orphan `70d96d3a` is gone with its scope. Re-running into the clean (recreated) scope grants each tuple under the AVM-deterministic name with nothing to collide against. This is the fastest unblock and should be tried first.

**Durable hardening (exact Bicep before/after) — fix the static-salt OpenAI grants.** This is the one declaration in the file that is non-idempotent independent of stale state. Key the assignment name on the actual principalId + scope resourceId (the canonical Azure / AVM pattern `guid(scopeResourceId, principalId, roleDefinitionId)`):

Before (`v2/infra/main.bicep` L1038-1048):

```bicep
resource searchOpenAiUserOnFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi) {
  name: guid(aiServicesName, 'search-system-mi', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: aiServicesAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: aiSearch!.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}
```

After:

```bicep
resource searchOpenAiUserOnFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi) {
  name: guid(aiServicesAccount.id, aiSearch!.outputs.systemAssignedMIPrincipalId!, subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))
  scope: aiServicesAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: aiSearch!.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}
```

Apply the same change to `searchOpenAiUserOnReusedOpenAi` (L1050) — swap `guid(existingOpenAiName, 'search-system-mi', '5e0bd9bd-…')` for `guid(existingOpenAi.id, aiSearch!.outputs.systemAssignedMIPrincipalId!, subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'))`.

Caveat: this is a name change, so on an existing deployment it creates a new assignment and orphans the old static-salt one (no conflict, just a stray to clean up once). It does not by itself clear the AVM-array orphan that blocked this run — that is handled by the re-run or the fallback delete below.

Note on the AVM `aiSearch` array: its names are AVM-deterministic and stable across runs, so no per-entry change is required for single-run idempotency. The residual cross-run hazard is the **divergent name formula between the AVM path (principalId salt) and the inline `existingSearch*` path (resource-NAME salt)** for the same logical grants. If a future tenant flips `useExistingSearch`, those paths produce different names for the same tuple and re-collide. Optional hardening: align the two paths on one `guid(searchResourceId, principalId, roleDefId)` formula. Raise as its own task — structural and out of scope for this unblock.

**Fallback operator unblock (only if a stale orphan persists on re-run).** Delete the conflicting assignment by the full id reported in the `RoleAssignmentExists` message, then re-run `azd provision`:

```bash
az role assignment delete --ids "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Search/searchServices/srch-<SUFFIX>/providers/Microsoft.Authorization/roleAssignments/70d96d3a-34c9-4887-8eb2-04191fdec8b1"
```

If a different orphan id appears on a subsequent run, discover and delete it at the reported scope:

```bash
az role assignment list --scope "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Search/searchServices/srch-<SUFFIX>" -o table
az role assignment delete --ids "<full id from the RoleAssignmentExists message>"
```

Resolve `<AZURE_SUBSCRIPTION_ID>`, `<RESOURCE_GROUP>`, and `<SUFFIX>` from `azd env get-values` in the active env. (As of this research the search service is `ResourceNotFound`, so the delete returns no-op and the plain re-run is sufficient.)

## Evidence

- Failed top-level deployment `<AZD_ENV_NAME>-<timestamp>`; failed nested deployment `avm.res.search.search-service.<SUFFIX>`; error `RoleAssignmentExists` id `70d96d3a34c948878eb204191fdec8b1`.
- `az deployment operation group list --name avm.res.search.search-service.<SUFFIX> -g <RESOURCE_GROUP>` → 10 ops all Succeeded; 5 roleAssignments Created (`59cd631c`, `2b069a0f`, `dc5e220f`, `45f6571e`, `7c263c6c`); none is `70d96d3a`.
- `az role assignment list --scope <aiServicesAccount>` → 0 assignments; `70d96d3a` not found at AI-account, search, or subscription scope (scope rolled back).
- `v2/infra/main.bicep`: deployer principal vars L258-259; `aiServicesName = 'aisa-${solutionSuffix}'` L522; `aiSearch` module + `roleAssignments` array L899-953; inline `existingSearch*` L992/1002/1012; `searchOpenAiUserOnFoundry`/`…OnReusedOpenAi` L1038/1050.
- Git pickaxe: `a598c761` (static-salt OpenAI grant), `f6d73556` (deployer entry), `d6b3bdf0` (AVM search module).
- AVM module: `avm/res/search/search-service:0.12.0`; default role-assignment name `guid(searchService.id, principalId, roleDefinitionId)`.

## Recommended next research (not completed)

- [ ] Confirm whether the AVM search-service module version was bumped between the two deployments into `<RESOURCE_GROUP>` (would prove the rename mechanism for the orphan).
- [ ] Confirm whether `azd down` or a manual delete removed the search service after the failed run (explains why the orphan scope is now `ResourceNotFound`).
- [ ] Decide whether to unify the AVM-path (principalId salt) and inline `existingSearch*`-path (resource-NAME salt) name formulas — separate hardening task, structural.
- [ ] Review `v2/infra/modules/ai-project.bicep` L65 `projectAiUserRole` (unconditional) and the other non-search `roleAssignments` arrays for the same static-salt anti-pattern.

## Clarifying questions

1. Was the search service `srch-<SUFFIX>` deleted (via `azd down` or manually) after the failed run? Its scope now returns `ResourceNotFound`, which is why a plain re-run should succeed.
2. Was the AVM `search-service` module version changed between deployments into this resource group? This is the most likely source of the divergent assignment name behind the orphan.
3. Has `useExistingSearch` ever been `true` for any prior deployment into this RG? If so, the inline NAME-salt path created the same tuples under different names — a second source of cross-run orphans.
