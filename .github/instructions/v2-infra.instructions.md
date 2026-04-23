---
description: "CWYD v2 Bicep + azd infrastructure conventions. Use when: editing v2/infra/**, adding a Bicep module, wiring main.bicep, adding outputs, configuring RBAC, adding a managed identity role assignment, adjusting azure.yaml, choosing a SKU, enabling WAF flags, or preparing for azd up."
applyTo: "v2/infra/**"
---

# v2 Infrastructure (Bicep + azd) Conventions

## Stack

- Bicep only — no raw ARM JSON authoring (compiled `.json` artifacts are fine).
- `azd` ≥ 1.18 (excluding 1.23.9 per repo memory).
- Subscription-scope or resource-group-scope only — no management-group scope in v2.

## Module structure

- `main.bicep` — entry point, declares params, picks `databaseType`, calls modules.
- `main.parameters.json` — default parameters; no secrets.
- `modules/<service>.bicep` — one resource family per module. Existing list in [v2/docs/development_plan.md](../../v2/docs/development_plan.md) §3.4.

## Rules

1. **No Key Vault for app secrets.** Auth = Managed Identity + RBAC. Connection info passed via `azd` env vars from Bicep outputs.
2. **User-Assigned Managed Identity** for every compute resource. Created once in `identity.bicep`; consumed by container apps, web apps, functions.
3. **Every module exports outputs** that `main.bicep` re-exports for `azure.yaml` to wire into runtime env vars.
4. **Conditional modules** for `databaseType`: `cosmosdb.bicep` vs `postgresql.bicep`. `main.bicep` invokes one or the other; never both.
5. **WAF flags** drive SKU/redundancy: `enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`. Defaults all `false` (cheapest dev path).
6. **Region allowlist:** `australiaeast`, `eastus2`, `japaneast`, `uksouth` (paired regions for redundancy).
7. **`azd up` must succeed at the end of every phase.** If a phase requires a new resource, the module lands with the phase — not later.
8. **Naming:** all resource names derived from `abbreviations.json` + `resourceToken` (`uniqueString(resourceGroup().id)`). No hand-typed names.

## RBAC pattern

```bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: targetResource
  name: guid(targetResource.id, identity.id, roleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
```

Use the `azure-rbac` skill or known role IDs — never invent role GUIDs.

## Validation

- `bicep build v2/infra/main.bicep` must produce no warnings classified as errors.
- `az deployment sub what-if` (or `group what-if`) must be clean before `azd up`.
- The CI image (`v2/docker/Dockerfile.ci-validate`) runs both above on every PR.

## Banned

- Inline secrets / connection strings in parameters or outputs.
- Hardcoded resource names.
- `Microsoft.Web/sites/config/appsettings` writes containing literal keys.
