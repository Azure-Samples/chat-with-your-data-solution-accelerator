# ADR 0019 — No environment-specific content in tracked files

- **Status**: Accepted
- **Date**: 2026-06-05
- **Phase**: 7 (close-out, repository hygiene)
- **Pillar**: Configuration Layer
- **Supersedes / amends**: none
- **Enforced by**: Hard Rule #18 in [.github/copilot-instructions.md](../../../.github/copilot-instructions.md)

## Context

While preparing the v2 MVP for public consumption a hygiene sweep on 2026-06-05 found multiple tracked files leaking real environment identifiers:

- Azure subscription GUID, tenant GUID, UAMI client/principal GUIDs.
- Azure resource group name, azd environment name, deployment suffix, and resource-specific names that embed the suffix.
- Cross-resource-group App Insights name + RG (from a probe ADR).
- The Container Apps Environment's deterministic FQDN fragment (`<random>.<region>.azurecontainerapps.io`).
- A developer UPN (`user@<tenant>.onmicrosoft.com`) and a Windows user profile path.
- A v1 evaluator dataset (`tests/llm-evaluator/data/dataset.jsonl`) containing 29 SAS URLs against a development storage account, with the tenant GUID embedded in the SAS payload.

None of these belong in source control. They tie the public sample to one person's lab, leak organizational topology, and create indefinite cleanup work every time a new environment is provisioned. The git history retains the worst of it, but the working tree must stop adding to it.

A parallel concern: a stray `bicep-errors.txt` file written by an IDE task was about to be tracked. Single-developer artifacts of that shape have no place in the repo either.

## Decision

Tracked files (source, tests, docs, ADRs, runbooks, Bicep / Terraform comments, fixtures, CI workflows) contain **only generic development and deployment guidance**. Real environment values live exclusively in:

- `.azure/<AZD_ENV_NAME>/.env` — gitignored by `azd` convention.
- The operator's `az` / `azd` CLI session — discovered with `azd env get-values` or `az account show`.
- Azure Resource Manager — discovered with `az resource show` / `az deployment sub show`.

When a tracked file needs to reference an environment value to make an example legible, it uses a placeholder from the table below — never a real value, even one belonging to a "throwaway" lab.

### Placeholder convention

| Placeholder | Replaces |
|---|---|
| `<AZURE_SUBSCRIPTION_ID>` | Azure subscription GUID |
| `<AZURE_TENANT_ID>` | Microsoft Entra tenant GUID |
| `<AZURE_PRINCIPAL_UPN>` | `user@tenant.onmicrosoft.com` or other UPN |
| `<AZURE_PRINCIPAL_OBJECT_ID>` | Entra user / service principal object ID |
| `<AZURE_UAMI_CLIENT_ID>` | User-Assigned Managed Identity client ID |
| `<AZURE_UAMI_PRINCIPAL_ID>` | User-Assigned Managed Identity principal (object) ID |
| `<RESOURCE_GROUP>` | Azure resource group name |
| `<AZD_ENV_NAME>` | The `azd` environment name |
| `<SUFFIX>` | The deployment suffix on app-tier resources (Container App, App Service, Function App, Foundry account / project, etc.) |
| `<DATA_SUFFIX>` | The deployment suffix on data-tier resources (Storage, Cosmos, Search, etc.) — distinct when separate deployments share data |
| `<REGION>` | Azure region (e.g. `eastus2`) |
| `<ACA_ENV_DOMAIN>` | The Container Apps Environment's auto-generated subdomain (the `<random>` in `<random>.<region>.azurecontainerapps.io`) |
| `<APPI_NAME>` / `<APPI_RESOURCE_GROUP>` | Cross-RG Application Insights account + its resource group |
| `<SAMPLE_STORAGE_ACCOUNT>` | Storage account name in sample / fixture URLs |
| `<INTERNAL_IP>` | Any non-RFC-reserved internal IP address |

This list is the canonical set. New placeholders may be added by amending this ADR (no code change required to introduce them, since they are pure documentation tokens).

### Exclusions (what does **not** count as env-specific)

These categories are allowed in tracked files unchanged:

- **RFC 1918 / IANA-reserved IP literals** (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.1`, `0.0.0.0`, `169.254.0.0/16`) — these document network topology, not a specific environment.
- **AVM / SDK example placeholders** carried over from upstream documentation (e.g. `124.56.78.91` in an AVM `@description`).
- **All-zero / well-known sentinel GUIDs** (`00000000-0000-0000-0000-000000000000`, role definition GUIDs, role assignment built-in IDs).
- **Synthetic test-fixture identifiers** that obviously cannot be real (e.g. `cwyd001` suffix in `v2/tests/**`, mock UUIDs like `500e77bd-26b9-441a-8fe3-cd0e02993671`).
- **Public Microsoft sample infrastructure** owned by the upstream repo (e.g. `cwydcontainerreg.azurecr.io` in `docs/container_registry_migration.md` and the v1 image-build workflow).
- **API version literals** (`2024-12-01-preview`, `2025-04-01-preview`) — these pin SDK behavior, not environments (already carved out by Hard Rule #16(e)).

### `.gitignore` companion

Files that local tooling writes per-developer must be gitignored, not removed-and-re-added. `v2/.gitignore` carries `bicep-errors.txt` for this reason.

## Consequences

**Positive.**

- Public consumers can clone the repo without inheriting one developer's lab identifiers.
- Onboarding docs document a procedure (`azd env get-values`), not a single environment.
- Renaming or rebuilding the dev environment never requires a doc sweep.
- Reduces the surface for accidental credential or topology leaks.

**Negative / cost.**

- One-time scrub work (already absorbed on 2026-06-05).
- Docs that quote real CLI output must redact before pasting — slightly higher friction than copy-paste.
- The placeholder set grows over time; this ADR is the index.

## Enforcement

Hard Rule #18 in [.github/copilot-instructions.md](../../../.github/copilot-instructions.md) binds all agents and contributors. A periodic audit `git grep` walks the patterns the 2026-06-05 sweep used; the canonical recipe is at the bottom of this ADR. CI gating is **not** in scope for this ADR (would require a per-pattern allow-list and the false-positive surface is large — see the Exclusions list); the sweep is operator-driven.

### Audit recipe

```powershell
# Run from repo root. Returns lines that should be reviewed; expect zero
# real-environment hits after applying the placeholder convention.
git grep -nIE '\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b' `
  | Select-String -NotMatch '00000000-0000-0000-0000-000000000000','b24988ac-6180-42a0-ab88-20f7382dd24c'

git grep -nIE 'cwyd[0-9a-z-]+\.(azurewebsites|azurecontainerapps|search\.windows|openai\.azure|cognitiveservices\.azure|blob\.core\.windows|documents\.azure|vault\.azure|azurecr\.io)' `
  | Select-String -NotMatch 'cwyd001','cwydcontainerreg'

git grep -nI 'onmicrosoft\.com' `
  | Select-String -NotMatch 'AZURE_PRINCIPAL_UPN','example'
```
