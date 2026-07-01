<!-- markdownlint-disable-file -->
# Research: azd Ephemeral Environment Teardown + Rebuild Runbook (CWYD v2)

Status: Complete (1 minor gap noted in Q2 — see "Known gap")

Scope: read-only research. No code changed. All Azure identifiers are placeholder tokens per Hard Rule #18.

Sibling research already in-tree (do not duplicate): `.copilot-tracking/research/2026-06-30/cloud-env-morning-resilience-research.md` (parent task — subscription-disable root cause + cost levers + rebuild) and `.copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md` (the proven Phase-0/Phase-1 rebuild runbook this research formalizes into a script).

---

## Q1 — azd service definitions + hooks (`v2/azure.yaml`)

File: `v2/azure.yaml`.

azd manifest header: `name: chat-with-your-data-v2`; `infra.provider: bicep`, `infra.path: infra`, `infra.module: main` (lines 22-31). `requiredVersions.azd: ">= 1.18.0 != 1.23.9"` (line 27).

Typed-prompt `parameters:` block (lines 39-95) — surfaced by `azd up` / `azd provision`. These are the prompts `--no-prompt` must satisfy from existing env values:
- `databaseType` (default `cosmosdb`; allowed `cosmosdb` / `postgresql`) — lines 40-50.
- `azureAiServiceLocation` (default `eastus2`; region allow-list) — lines 52-66.
- `enableMonitoring` / `enableScalability` / `enableRedundancy` / `enablePrivateNetworking` (all default `false`) — lines 68-89.

### Services (lines 97-198)

| Service | project | language | host | image / build | service-scoped hooks |
| --- | --- | --- | --- | --- | --- |
| `backend` | `./src/backend` | `py` | `containerapp` | `docker.path: ../../docker/Dockerfile.backend`, `context: ../..`, `remoteBuild: true` (ACR remote build, no local Docker) — lines 110-122 | none |
| `frontend` | `./src/frontend` | `js` | `appservice` | build-from-source; `dist: ./build-output` — lines 123-167 | `prepackage` → `../../scripts/package-frontend.ps1` (windows) / `.sh` (posix), `continueOnError: false` — lines 159-167 |
| `function` | `./build-functions` | `py` | `function` | (zip deploy of regenerated `build-functions/`) | `prepackage` → `../scripts/prepackage-function.ps1` / `.sh`, `continueOnError: false` — lines 188-198 |

Service `prepackage` hooks are deliberately service-scoped (not project-scoped) so a targeted `azd deploy <service>` regenerates its artifact (BUG-0058 / BUG-0081 rationale in the file comments).

### Project-level hooks (lines 218-247)

- `postprovision` → `./scripts/post-provision.ps1` / `.sh`, `continueOnError: false`, `interactive: true` (lines 230-238). Wraps `v2/scripts/post_provision.py`: in postgresql mode runs `CREATE EXTENSION vector`; in cosmosdb mode ensures the Azure AI Search chat index; seeds the Foundry IQ Knowledge Base; prints an `AZURE_*` output summary. Idempotent, safe to re-run. **In private-networking mode it exits 7** because the deployer is outside the VNet (re-run via Bastion tunnel + `azd hooks run postprovision`).
- `postdeploy` → `./scripts/upload-sample-data.ps1` / `.sh`, **`continueOnError: true`**, `interactive: true` (lines 239-247). Wraps `v2/scripts/upload_sample_data.py` (sample-data seed).

### Does any hook clear the registry endpoint / purge / seed?

- **Endpoint clearing:** NO hook clears `AZURE_CONTAINER_REGISTRY_ENDPOINT`. There is no `preprovision` hook at all. This is the gap WI-04 (Q6) targets.
- **Purging soft-deletes:** NO hook purges Cognitive Services. Not azd's job during `up`/`provision`.
- **Seeding:** YES — `postdeploy` (`upload_sample_data.py`) is the sample-data seed.

### The postdeploy seed prompt + how to suppress it

`v2/scripts/upload_sample_data.py` (module docstring lines 1-33 + `_MENU` / selection logic lines 88-205). Selection precedence: `--set` arg → `AZURE_ENV_SAMPLE_DATA` env override → interactive menu (only when the hook runs in a TTY). Menu rows (`_MENU`, lines 97-104): `1) default`, `2) contract`, `3) employee`, `4) all` (default key `4`), `0) none`. Accepted tokens (`_SELECTION_TOKENS`, lines 76-87): `default | contract | employee | all | none | skip`.

Suppression options (any one works):
- **`azd up --no-prompt`** — the cleanest. azd runs hooks non-interactively; `upload_sample_data.py`'s docstring states "a non-interactive shell with no override seeds the default PDF document set" (it does NOT block on the menu). So `--no-prompt` will NOT hang — but it WILL seed the `default` set unless overridden.
- **`azd env set AZURE_ENV_SAMPLE_DATA none`** (or `skip`) before `azd up` — opt out of seeding entirely (no documents uploaded). This is the right choice for a fast morning rebuild where you don't want to re-seed.
- **`azd env set AZURE_ENV_SAMPLE_DATA all`** (or `default` / `contract` / `employee`) — seed unattended with an explicit scope.
- The hook is `continueOnError: true`, so even a seed failure never fails `azd up`.

> Morning-rebuild recommendation: set `AZURE_ENV_SAMPLE_DATA` explicitly (e.g. `all` if you want grounding docs back, or `none` for a bare rebuild) so the seed is deterministic and never waits on a menu.

---

## Q2 — `azd down` vs `--purge` vs `--force --purge`

Source: Microsoft Learn azd reference (https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/reference, `ms.date` 2026-06-12) — `azd down [<layer>] [flags]`:
- `--force` — "Does not require confirmation before it deletes resources."
- `--purge` — "Does not require confirmation before it permanently deletes resources that are soft-deleted by default (for example, key vaults)."
- Inherited: `--no-prompt`, `-e/--environment`, `-C/--cwd`, `--debug`.

Behavior:
- `azd down` — deletes the deployment's resources; **prompts** for confirmation; soft-deletable resources are left in the soft-deleted state (recoverable, but block name reuse).
- `azd down --purge` — same delete, **plus** permanently purges the soft-deletable resources azd recognizes, **without** a purge confirmation.
- `azd down --force --purge` — no confirmation for either the delete or the purge (fully unattended). This is the form a script should use.

### Does `--purge` purge soft-deleted Cognitive Services?

**YES — azd's `--purge` path does purge Cognitive Services accounts**, confirmed in azd source (`Azure/azure-dev`):
- `cli/azd/pkg/azapi/cognitive_service.go` → `func (cli *AzureClient) PurgeCognitiveAccount(...)`.
- `cli/azd/pkg/infra/provisioning/bicep/bicep_provider.go` → builds an `itemToPurge{ resourceType, ..., purge: p.purgeCognitiveAccounts(...), cognitiveAccounts: groupByKind[name] }`.

So azd's purge coverage is broader than the doc's "(for example, key vaults)" wording — it includes **Key Vault, App Configuration, API Management, and Cognitive Services** (AI Services / OpenAI / Content Safety / Speech are all `Microsoft.CognitiveServices/accounts` kinds and are grouped by kind in `groupByKind`).

### Known gap (the reason the manual purge is still needed in CWYD)

azd can only purge **what it just deleted in that `azd down` run**. It enumerates the soft-deletable accounts from the deployment's live resource set, deletes them, then purges them. **If the resource group was already emptied out-of-band** (the overnight subscription-disable wipe — see the parent research: zero `…/delete` activity-log events, resources vanished via the billing plane), then by the time you run `azd down`:
- there is nothing in the deployment for azd to enumerate/delete, so
- azd's purge step has an empty `cognitiveAccounts` list and purges nothing, while
- the platform-side soft-delete shadows (`aisa-<SUFFIX>`, `cs-<SUFFIX>`, `spch-<SUFFIX>`) persist and block the next provision with `FlagMustBeSetForRestore`.

This is exactly what BUG-0054 observed (`.copilot-tracking/research/2026-06-30/bug-0054-live-close-research.md` line 23: the 3 soft-deleted accounts had to be purged manually). **Conclusion: keep the explicit `az cognitiveservices account purge` step in the morning script** — it is the durable safety net for the overnight-wipe case, where azd-purge cannot help because azd never deleted anything. For a *self-initiated* evening `azd down --force --purge` (resources still live), azd-purge WILL clear them, but the morning script must still defensively purge because it cannot assume the evening teardown ran (or ran cleanly).

> Net: `azd down --purge` does NOT *reliably* eliminate the manual purge in this environment — not because azd lacks the capability, but because the overnight wipe removes the resources before any `azd down` can enumerate them. The manual `az cognitiveservices account purge` stays.

---

## Q3 — What azd env state survives `azd down`?

`azd down` deletes Azure resources only. It does **not** delete or reset the local environment under `.azure/<env>/` — the env (`.azure/<env>/.env` + `config.json`) survives, including the `AZURE_*` outputs captured by the last successful provision. (Removing the env is a separate explicit command: `azd env remove <env>`.)

Therefore, after `azd down` (or after the overnight wipe, which never touches the local `.azure/` folder at all):
- `AZURE_CONTAINER_REGISTRY_ENDPOINT` — **SURVIVES as a non-empty value** (e.g. `cr<suffix>.azurecr.io`). On the next `azd up`, `main.parameters.json` line 110-111 binds `backendContainerRegistryHostname` to `${AZURE_CONTAINER_REGISTRY_ENDPOINT=}`, so the Container App image resolves to `<registry>/cwyd-backend:latest` against a **freshly recreated, empty ACR** → `MANIFEST_UNKNOWN` → Container App `Failed`. **The chicken-and-egg re-fires.** → The morning script MUST clear it.
- `AZURE_ENV_INGESTION_TRIGGER` — survives (azd-env value; BUG-0054 re-asserts `event_grid` defensively each rebuild because an unset value silently falls back to `direct_enqueue` and certifies the wrong path; `main.parameters.json` lines 20-21 → `main.bicep` line 100 default `direct_enqueue` → line 1949 Container App env).
- `AZURE_SOLUTION_SUFFIX` and all other captured outputs — survive.

> **Answer to the headline question: YES, `AZURE_CONTAINER_REGISTRY_ENDPOINT` survives `azd down` (and the overnight wipe), so the morning script must clear it (`azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT ""`) before the first `azd up`.** This is the single most important morning step after the subscription gate.

---

## Q4 — Robust clean-rebuild ordering + other soft-delete-protected resource types

Confirmed ordering (formalized from `bug-0054-live-close-details.md` Phase 0 + Phase 1):

1. **Subscription Enabled + write probe (HARD GATE — STOP if read-only).**
   - `az account list --all --refresh --query "[?id=='<AZURE_SUBSCRIPTION_ID>'].state" -o tsv` must be `Enabled`. (`az account show` has NO `--refresh`; use `list --all --refresh`.)
   - Reversible write probe (authoritative — a `Warned` state can still deny writes): `az tag update --resource-id /subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP> --operation merge --tags cwydWriteProbe=ok` then revert with `--operation delete`. `ReadOnlyDisabledSubscription` ⇒ STOP and tell the user to re-enable the subscription (billing action, not a CLI fix).
2. **Purge soft-deleted Cognitive Services for the suffix** (clears `FlagMustBeSetForRestore`):
   - `az cognitiveservices account list-deleted --query "[?contains(name,'<SUFFIX>')].{name:name,location:location}" -o json`, then for each: `az cognitiveservices account purge --location <REGION> --resource-group <RESOURCE_GROUP> --name <NAME>`. (Purge is keyed by the *original* location + RG even though the account is already deleted.)
3. **Clear the registry endpoint** so the placeholder image is used on first provision: `azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT ""` (and re-assert `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` if that cutover intent must hold).
4. **`azd up --no-prompt`** — package → provision (placeholder image, recreates ACR + all infra, captures the new ACR endpoint back into the env) → deploy (remote-builds + pushes the real images, the `azd-service-name: backend` tag-swap patches the live revision to the real ACR image). ~30-40 min.
5. **Confirm Container App `Succeeded` + `Running` + real image, and backend `/api/health` = 200:**
   - `az containerapp show -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --query "{state:properties.provisioningState,running:properties.runningStatus,image:properties.template.containers[0].image,fqdn:properties.configuration.ingress.fqdn}" -o json`.
   - `Invoke-WebRequest https://<BACKEND_FQDN>/api/health`.

### Other soft-delete-protected resource types in this deployment?

- **Key Vault: NONE.** `v2/infra` declares **no `Microsoft.KeyVault/vaults` resource** (grep across `v2/infra/**` returns only the `kv-` abbreviation in `abbreviations.json` lines 201-202 — never instantiated). This matches the repo's no-Key-Vault-for-app-secrets rule. So there is no Key Vault soft-delete / purge-protection to clear. `v2/docs/infrastructure.md` line ~270 confirms: "`--purge` removes soft-deleted Cognitive Services, Key Vault (none here), and App Configuration".
- **No App Configuration** (`Microsoft.AppConfiguration`) resource is declared either.
- **Cognitive Services accounts are the ONLY soft-delete-protected type here.** Four `Microsoft.CognitiveServices/accounts` are created in `v2/infra/main.bicep`, all `disableLocalAuth: true`:
  - `kind: 'AIServices'` (line 535) → `aisa-<SUFFIX>`
  - `kind: 'SpeechServices'` (line 773) → `spch-<SUFFIX>`
  - `kind: 'ContentSafety'` (line 848) → `cs-<SUFFIX>`
  - plus the AI Services / OpenAI account at line ~344 (also a CognitiveServices account).
  - All are purged by the same `az cognitiveservices account purge` loop (step 2). The three observed in BUG-0054 were `aisa-`, `cs-`, `spch-`.
- PostgreSQL Flexible Server (postgresql mode), Cosmos DB, Azure AI Search, Storage, ACR, Container Apps, App Service, Function App — **none are soft-delete-protected** in a way that blocks a same-name reprovision here (no purge step needed). Cosmos has its own soft-delete behavior but is not in the observed blocker set.

---

## Q5 — Existing teardown / rebuild / recovery scripts or Makefile targets to extend

There is **NO existing teardown or rebuild script** in the repo. Inventory:

- `v2/scripts/` (file_search) — `package-frontend.ps1/.sh/.py`, `post-provision.ps1/.sh`, `post_provision.py`, `prepackage-function.ps1/.sh/.py`, `upload-sample-data.ps1/.sh`, `upload_sample_data.py`, `tests/`. **All are azd lifecycle hooks (package / postprovision / postdeploy). None do teardown, purge, subscription-gating, or health-poll rebuild.**
- `v2/Makefile` — only `typecheck` (`uv run pyright`), `test` (`uv run pytest`), `lint` (`black --check` + `flake8`). **No `up` / `down` / `rebuild` / `teardown` target.**
- Root `scripts/` — v1-only (`checkquota.sh`, `disable_auth.sh`, `post_deployment_setup.*`, `parse_env.*`, `validate_bicep_params.py`, `data_scripts/`). Not v2; do not extend for this.
- The only formalized rebuild "runbook" today is prose in `.copilot-tracking/details/2026-06-30/bug-0054-live-close-details.md` (Phase 0 + Phase 1) and a one-liner teardown in `v2/docs/infrastructure.md` §7.4 (`azd down --purge`).

> **Greenfield for the scripts.** New `morning-rebuild.ps1` / `evening-teardown.ps1` should land under `v2/scripts/` (sibling to the existing hook scripts) — but adding new top-level script files is a structural addition: per Hard Rule #10, confirm placement with the user before the implementer creates them. A `v2/Makefile` `rebuild:` / `teardown:` target wrapping them would be a natural, low-risk convenience addition.

---

## Q6 — WI-04 feasibility: auto placeholder image on first provision (drop the manual endpoint-clear)

Today the Container App image is gated purely on whether `backendContainerRegistryHostname` (bound to `AZURE_CONTAINER_REGISTRY_ENDPOINT`) is empty (`v2/infra/main.bicep` lines 1829-1831):
```bicep
image: empty(backendContainerRegistryHostname)
  ? 'mcr.microsoft.com/k8se/quickstart:latest'
  : '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
```
The bug is that the endpoint env var *survives* teardown/wipe (Q3), so on a fresh provision it's non-empty while the recreated ACR is empty → real-image path → `MANIFEST_UNKNOWN`. Three candidate approaches:

**Option A — `preprovision` hook that clears the endpoint when the ACR/image is absent (RECOMMENDED, lowest blast radius).**
Add a project-level `preprovision` hook (none exists today) that, before every provision, checks whether the backend image actually exists in the registry and, if not, clears `AZURE_CONTAINER_REGISTRY_ENDPOINT` in the azd env. Logic: if `AZURE_CONTAINER_REGISTRY_ENDPOINT` is set, `az acr repository show -n cr<SUFFIX> --image cwyd-backend:latest` (or `az acr show -n cr<SUFFIX>` for existence); on any failure (ACR gone, repo/tag missing, sub read-only) `azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT ""`. Idempotent, self-healing, makes `azd up` a true one-command rebuild with no manual pre-step. Cost: one more hook + a small Python/script file (structural addition → Hard Rule #10 confirm). This is the cleanest and is exactly what the morning script does inline, just promoted into the azd lifecycle so a bare `azd up` also self-heals.

**Option B — Bicep gate on image existence (NOT feasible cleanly).** Bicep cannot query "does this tag exist in ACR" at compile/deploy time — there is no resource/function to test image presence, and `existing` references to a registry don't expose repository/tag manifests. A deployment script (`Microsoft.Resources/deploymentScripts`) could probe ACR and output a boolean, but that adds a container-backed deployment-script resource (cost, identity, latency, complexity) and an intra-template ordering dependency — heavier and more fragile than Option A. Not recommended.

**Option C — Two-phase param (split first-provision from steady-state).** Keep a separate `forcePlaceholderImage` bool param defaulting to detection-by-hook. Collapses into Option A anyway. No advantage.

**Verdict: WI-04 is FEASIBLE via Option A (a `preprovision` hook that clears `AZURE_CONTAINER_REGISTRY_ENDPOINT` when the backend image is not actually present in ACR).** It removes the need for the manual endpoint-clear and makes `azd up` self-healing for the daily-wipe case. It is a structural addition (new hook + script) → assess/confirm placement per Hard Rule #10 before implementing. The Bicep-side gate (Option B) is not cleanly feasible. Until WI-04 lands, the morning script's explicit clear (Q3/Q7) is the workaround.

---

## Q7 — Draft scripts (placeholder tokens only; idempotent + safe)

> These are DESIGN DRAFTS for the research record, not committed code. Real values come from `azd env get-values` at runtime; never hard-code Azure IDs (Hard Rule #18). Both scripts are idempotent and re-runnable.

### `morning-rebuild.ps1`

```powershell
#Requires -Version 7
<#
.SYNOPSIS
  One-command CWYD v2 cloud rebuild from an empty / torn-down state.
.DESCRIPTION
  1. Subscription Enabled gate + reversible write probe (STOP if read-only).
  2. Purge soft-deleted Cognitive Services for the suffix (clears FlagMustBeSetForRestore).
  3. Clear AZURE_CONTAINER_REGISTRY_ENDPOINT so the first provision uses the placeholder image.
  4. azd up --no-prompt (provision placeholder -> capture ACR -> deploy real images).
  5. Poll Container App provisioningState/runningStatus + backend /api/health; print the endpoint.
  Idempotent: safe to re-run. Performs NO git operations.
.NOTES
  Run from v2/. Requires: az, azd, an authenticated session. Real values resolved from the azd env.
#>
[CmdletBinding()]
param(
  [string]$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID,   # or pass explicitly
  [string]$ResourceGroup,                                  # default: from azd env AZURE_RESOURCE_GROUP
  [string]$Suffix,                                         # default: from azd env AZURE_SOLUTION_SUFFIX
  [string]$Region,                                         # default: from azd env AZURE_LOCATION
  [ValidateSet('none','default','contract','employee','all')]
  [string]$SampleData = 'none',                            # seed scope for the postdeploy hook
  [switch]$SkipPurge,                                      # skip the Cognitive Services purge sweep
  [int]$HealthTimeoutSec = 600
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-AzdValue([string]$key) {
  $line = (azd env get-values 2>$null) | Select-String "^$key="
  if (-not $line) { return '' }
  return ($line.ToString() -replace "^$key=", '').Trim('"')
}

# --- Resolve env-derived defaults (placeholders until azd env provides them) ---
if (-not $ResourceGroup) { $ResourceGroup = Resolve-AzdValue 'AZURE_RESOURCE_GROUP' }
if (-not $Suffix)        { $Suffix        = Resolve-AzdValue 'AZURE_SOLUTION_SUFFIX' }
if (-not $Region)        { $Region        = Resolve-AzdValue 'AZURE_LOCATION' }
if (-not $SubscriptionId){ $SubscriptionId= Resolve-AzdValue 'AZURE_SUBSCRIPTION_ID' }
foreach ($p in 'SubscriptionId','ResourceGroup','Suffix','Region') {
  if (-not (Get-Variable $p -ValueOnly)) { throw "Missing required value: $p (pass -$p or set the azd env)." }
}
Write-Host "Rebuild target: sub=$SubscriptionId rg=$ResourceGroup suffix=$Suffix region=$Region" -ForegroundColor Cyan

# === Step 1: subscription Enabled gate + reversible write probe (HARD STOP) ===
$state = az account list --all --refresh --query "[?id=='$SubscriptionId'].state" -o tsv
if ($state -ne 'Enabled') {
  throw "Subscription state is '$state' (not Enabled). Re-enable it in the portal (remove spending limit / reactivate), then re-run. No Azure writes attempted."
}
$rgId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
try {
  az tag update --resource-id $rgId --operation merge --tags cwydWriteProbe=ok 1>$null 2>$null
  az tag update --resource-id $rgId --operation delete --tags cwydWriteProbe=ok 1>$null 2>$null
} catch {
  throw "Write probe failed (likely ReadOnlyDisabledSubscription). Subscription is read-only despite state '$state'. Re-enable and re-run. No further writes attempted."
}
Write-Host "Subscription Enabled + writable." -ForegroundColor Green

# === Step 2: purge soft-deleted Cognitive Services for the suffix (idempotent) ===
if (-not $SkipPurge) {
  $deleted = az cognitiveservices account list-deleted `
    --query "[?contains(name,'$Suffix')].{name:name,location:location,rg:resourceGroup}" -o json | ConvertFrom-Json
  if ($deleted) {
    foreach ($acct in $deleted) {
      $loc = if ($acct.location) { $acct.location } else { $Region }
      $rg  = if ($acct.rg)       { $acct.rg }       else { $ResourceGroup }
      Write-Host "Purging soft-deleted Cognitive Services: $($acct.name) ($loc)" -ForegroundColor Yellow
      az cognitiveservices account purge --location $loc --resource-group $rg --name $acct.name 1>$null
    }
  } else {
    Write-Host "No soft-deleted Cognitive Services for suffix '$Suffix'." -ForegroundColor Green
  }
}

# === Step 3: clear the registry endpoint so first provision uses the placeholder image ===
azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "" 1>$null
azd env set AZURE_ENV_SAMPLE_DATA $SampleData 1>$null   # deterministic seed scope (none = bare rebuild)
Write-Host "Cleared AZURE_CONTAINER_REGISTRY_ENDPOINT; AZURE_ENV_SAMPLE_DATA=$SampleData." -ForegroundColor Green

# === Step 4: azd up (provision placeholder -> capture ACR -> deploy real images) ===
$env:AZD_SKIP_UPDATE_CHECK = '1'
Write-Host "Running azd up --no-prompt (this takes ~30-40 min)..." -ForegroundColor Cyan
azd up --no-prompt
if ($LASTEXITCODE -ne 0) { throw "azd up failed (exit $LASTEXITCODE). Inspect output above." }

# === Step 5: confirm Container App + backend health ===
$appName = "ca-backend-$Suffix"
$deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
do {
  $app = az containerapp show -g $ResourceGroup -n $appName `
    --query "{state:properties.provisioningState,running:properties.runningStatus,image:properties.template.containers[0].image,fqdn:properties.configuration.ingress.fqdn}" -o json | ConvertFrom-Json
  if ($app.state -eq 'Succeeded' -and $app.running -eq 'Running') { break }
  Start-Sleep -Seconds 15
} while ((Get-Date) -lt $deadline)
if (-not ($app.state -eq 'Succeeded' -and $app.running -eq 'Running')) {
  throw "Container App $appName not healthy in time (state=$($app.state) running=$($app.running) image=$($app.image))."
}
$fqdn = $app.fqdn
$healthDeadline = (Get-Date).AddSeconds($HealthTimeoutSec)
do {
  try {
    $resp = Invoke-WebRequest "https://$fqdn/api/health" -SkipHttpErrorCheck -TimeoutSec 15
    if ($resp.StatusCode -eq 200) { break }
  } catch { }
  Start-Sleep -Seconds 10
} while ((Get-Date) -lt $healthDeadline)
if (-not $resp -or $resp.StatusCode -ne 200) { throw "Backend /api/health did not return 200 in time (fqdn=$fqdn)." }

Write-Host "REBUILD COMPLETE. Backend: https://$fqdn  (/api/health=200, image=$($app.image))" -ForegroundColor Green
[console]::beep(880,200); [console]::beep(1175,250)
```

### `evening-teardown.ps1` (optional)

```powershell
#Requires -Version 7
<#
.SYNOPSIS
  Cost-control CWYD v2 teardown: azd down --force --purge, then verify the purge.
.DESCRIPTION
  Self-initiated evening teardown (resources still live, so azd-purge CAN clear the
  Cognitive Services accounts). Verifies no soft-deleted accounts remain for the suffix;
  purges any stragglers. Idempotent. Performs NO git operations. Leaves the .azure/<env>
  folder intact (AZURE_CONTAINER_REGISTRY_ENDPOINT will be cleared so the next rebuild
  is clean even if morning-rebuild is skipped).
#>
[CmdletBinding()]
param(
  [string]$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID,
  [string]$ResourceGroup,
  [string]$Suffix,
  [string]$Region,
  [switch]$Force   # required to actually tear down (guard against accidental runs)
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-AzdValue([string]$key) {
  $line = (azd env get-values 2>$null) | Select-String "^$key="
  if (-not $line) { return '' }
  return ($line.ToString() -replace "^$key=", '').Trim('"')
}
if (-not $ResourceGroup) { $ResourceGroup = Resolve-AzdValue 'AZURE_RESOURCE_GROUP' }
if (-not $Suffix)        { $Suffix        = Resolve-AzdValue 'AZURE_SOLUTION_SUFFIX' }
if (-not $Region)        { $Region        = Resolve-AzdValue 'AZURE_LOCATION' }
if (-not $SubscriptionId){ $SubscriptionId= Resolve-AzdValue 'AZURE_SUBSCRIPTION_ID' }

if (-not $Force) {
  Write-Host "DRY RUN. Would run: azd down --force --purge for sub=$SubscriptionId rg=$ResourceGroup. Re-run with -Force to execute." -ForegroundColor Yellow
  return
}

# Only attempt teardown if the subscription is writable (skip cleanly if already disabled).
$state = az account list --all --refresh --query "[?id=='$SubscriptionId'].state" -o tsv
if ($state -ne 'Enabled') {
  Write-Host "Subscription state '$state' (not Enabled) -- nothing to tear down (likely already wiped). Exiting." -ForegroundColor Yellow
  return
}

Write-Host "Tearing down (azd down --force --purge)..." -ForegroundColor Cyan
azd down --force --purge
# azd down exits non-zero if the RG is already gone; treat that as already-down.
if ($LASTEXITCODE -ne 0) { Write-Host "azd down returned $LASTEXITCODE (RG may already be empty)." -ForegroundColor Yellow }

# Verify purge; sweep any stragglers azd could not reach.
$deleted = az cognitiveservices account list-deleted `
  --query "[?contains(name,'$Suffix')].{name:name,location:location,rg:resourceGroup}" -o json | ConvertFrom-Json
foreach ($acct in ($deleted | Where-Object { $_ })) {
  $loc = if ($acct.location) { $acct.location } else { $Region }
  $rg  = if ($acct.rg)       { $acct.rg }       else { $ResourceGroup }
  Write-Host "Purging straggler: $($acct.name) ($loc)" -ForegroundColor Yellow
  az cognitiveservices account purge --location $loc --resource-group $rg --name $acct.name 1>$null
}

# Pre-clear the endpoint so a later azd up is clean even without morning-rebuild.
azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "" 1>$null
Write-Host "Teardown complete; soft-deletes purged; registry endpoint cleared." -ForegroundColor Green
[console]::beep(880,200); [console]::beep(1175,250)
```

Notes baked into the drafts:
- Subscription gate before any write (morning) / before teardown (evening); STOP if read-only.
- Cognitive Services purge is idempotent (empty list = no-op) and tolerant of the account's recorded location/RG.
- The endpoint clear is the chicken-and-egg fix and is done in BOTH scripts (so a skipped morning step is still safe).
- `AZURE_ENV_SAMPLE_DATA` is set explicitly so the postdeploy seed never blocks and is deterministic.
- Health poll has a bounded timeout and fails loudly.
- No git operations (git-ownership rule). No real Azure IDs (Hard Rule #18). Both end with the beep convention only as a script-local "done" chime (drop if running unattended in CI).

---

## Answers to the return questions (summary)

- **Does `azd down --purge` remove the soft-deleted Cognitive Services (so the manual purge can be dropped)?** azd's `--purge` *can* purge Cognitive Services (confirmed in azd source: `PurgeCognitiveAccount` / `purgeCognitiveAccounts`). **But it only purges what that same `azd down` run just deleted.** In the CWYD daily case the resources are wiped overnight by the subscription disable *before* any `azd down` runs, so azd has nothing to enumerate and the soft-deletes persist (`FlagMustBeSetForRestore`). **Keep the manual `az cognitiveservices account purge` step** — it's the durable fix for the overnight-wipe path.
- **Does `AZURE_CONTAINER_REGISTRY_ENDPOINT` survive `azd down`?** **YES.** `azd down` deletes Azure resources only; the local `.azure/<env>/.env` (and all captured outputs) survive. The non-empty endpoint re-fires the chicken-and-egg on the next `azd up`. **The morning script MUST clear it** (`azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT ""`).
- **WI-04 feasibility (auto placeholder image on first provision):** **FEASIBLE via a `preprovision` hook** that clears `AZURE_CONTAINER_REGISTRY_ENDPOINT` when the backend image is not actually present in ACR (Option A). The Bicep-side "gate on image existence" (Option B) is not cleanly feasible (Bicep cannot probe ACR manifests without a heavyweight deploymentScript). Implementing WI-04 is a structural addition (new hook + script) → confirm per Hard Rule #10.

## Clarifying questions for the user

1. Placement: should the new `morning-rebuild.ps1` / `evening-teardown.ps1` live under `v2/scripts/` (sibling to the hook scripts) with optional `v2/Makefile` `rebuild:` / `teardown:` targets? (Structural addition — Hard Rule #10.)
2. Default seed scope for the morning rebuild — `none` (fast bare rebuild) or `all` (re-seed grounding docs each morning)?
3. Do you want WI-04 (the self-healing `preprovision` endpoint-clear hook) implemented as part of this work, or kept as the manual script step for now?

## Recommended next research (not done here)

- [ ] Confirm `az cognitiveservices account purge` works for ALL four account kinds (AIServices / OpenAI / SpeechServices / ContentSafety) in this subscription's region(s) — some regions historically gated purge of certain kinds.
- [ ] Verify the exact `azd up` exit code + behavior when the subscription flips read-only mid-provision (graceful fail vs partial state) to harden the morning script's retry story.
- [ ] WI-04 implementation spike: prototype the `preprovision` hook's ACR-existence probe (`az acr repository show` vs `az acr show`) and confirm it no-ops cleanly when the sub is read-only (must not block provision when ACR genuinely exists).
