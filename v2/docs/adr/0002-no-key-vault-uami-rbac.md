# ADR 0002 — No Key Vault for app secrets — UAMI + RBAC + Bicep-output env vars

- **Status**: Accepted
- **Date**: 2026-04-22
- **Phase**: 1
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

CWYD v1 provisions an Azure Key Vault and stashes connection strings, account keys, and the Azure OpenAI API key into it. The backend pulls those secrets at startup via `DefaultAzureCredential` → `SecretClient.get_secret(...)`. This pattern is widespread in the older Azure samples canon and is what most readers expect.

It also has well-known costs:

1. **A whole resource (and its access policies / RBAC) to provision, monitor, and rotate** for the sole purpose of storing strings the application could reach without it.
2. **Extra startup latency and a runtime failure mode** (Key Vault throttling, transient AAD token failures during cold start) for every container replica.
3. **Two layers of authorization to debug** when access fails — RBAC on the target resource, *and* RBAC/access-policies on Key Vault itself.
4. **Secrets that aren't really secrets** — endpoint URIs, account names, deployment names, region codes are all non-sensitive Bicep outputs. Storing them in Key Vault gives the false impression they need protection.
5. **Account-key auth keeps the key-rotation problem alive** even though Cosmos DB, Storage, AI Search, Postgres, and AI Services all support Microsoft Entra ID auth.

Microsoft's own [Multi-Agent Custom Automation Engine](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) (MACAE) sample drops Key Vault entirely in favor of UAMI + RBAC + plain env vars, and reports lower deploy-time complexity and faster cold start as a result. The pattern is also what the Well-Architected Framework's Identity guidance prefers for greenfield workloads.

## Decision

**v2 does not provision Key Vault.** Application identity and configuration are wired as follows:

1. **One user-assigned managed identity (UAMI)** is provisioned in `infra/main.bicep` and attached to every compute resource that needs Azure access (App Service for backend, App Service for frontend if it proxies, Functions app).
2. **All data-plane access uses Microsoft Entra ID** — no account keys, no connection strings with embedded secrets:
   - Cosmos DB → `Cosmos DB Built-in Data Contributor` data-plane role on the UAMI.
   - Azure Storage → `Storage Blob Data Contributor`, `Storage Queue Data Contributor` on the UAMI.
   - Azure AI Search → `Search Index Data Contributor`, `Search Service Contributor` on the UAMI.
   - Foundry Project / AI Services → `Cognitive Services User`, `Azure AI Developer` on the UAMI.
   - PostgreSQL Flexible Server → Entra-ID admin grants; the UAMI's principal is added as a database role; the workload signs in with an Entra access token from `azure.identity.aio.DefaultAzureCredential`.
3. **Configuration travels as Bicep outputs → container env vars**, not as Key Vault references. Every `AZURE_*` env var consumed by `AppSettings` ([ADR 0003](0003-pydantic-settings-over-envhelper.md)) is a non-secret value: endpoint URI, deployment name, resource name, suffix, region. The `AZURE_UAMI_CLIENT_ID` env var carries the UAMI's client ID so the credential code can pin to it.
4. **Credentials are constructed via the `credentials` registry domain** ([`v2/src/providers/credentials/`](../../src/providers/credentials/)) — `managed_identity` in Azure (when `AZURE_UAMI_CLIENT_ID` is set), `cli` for local dev. See [ADR 0001](0001-registry-over-factory-dispatch.md) and [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md).

### Out of scope — what *would* legitimately need Key Vault

If a future Scenario Pack requires any of the following, it must propose a follow-up ADR re-introducing Key Vault for **only** that secret class:

- A real symmetric API key for a non-Microsoft service (e.g., a third-party LLM with no AAD support).
- TLS certificates for custom domains that aren't managed by Azure Front Door / App Service managed certificates.
- Customer-managed encryption keys (CMK) for at-rest encryption — those land in Key Vault by definition.

Adding Key Vault back for *any other reason* is a breaking change to this ADR and requires a new ADR superseding it.

## Consequences

### Positive

- **One fewer resource to provision, monitor, and pay for.** Removes the whole `Microsoft.KeyVault/vaults` block, its diagnostic settings, its private endpoint (when WAF mode is on), and its RBAC role assignments.
- **One authorization layer to debug.** Access failures point straight at the target resource's RBAC, not at a Key Vault intermediary.
- **Faster cold start.** No `SecretClient.get_secret` round trips at startup; settings load synchronously from `os.environ`.
- **No key rotation playbook needed.** AAD-issued tokens are short-lived and refreshed automatically by `azure.identity`.
- **Aligns with WAF Identity pillar** and with MACAE — the reference architecture maintainers already moved this direction.

### Negative

- **Customer forks that depend on a non-AAD external secret must re-introduce Key Vault** (or another secret store) themselves, and must do so via the supersession path above. This is a real cost for some integrations.
- **Local development needs Azure-CLI sign-in** (`az login`) so the `cli` credential provider can issue tokens against the same data-plane RBAC. We accept this in exchange for keeping the dev path identical to the prod path.
- **PostgreSQL Entra-ID auth requires a one-time admin step** to add the UAMI as a database role. Captured in `infra/main.bicep` (`postgresAdminPrincipalName` param + `_validatePostgresAdminPrincipalName` guard, P1.2 in `development_plan.md` §3.6.2).

### Neutral

- The `AZURE_OPENAI_API_KEY` env var that v1 used does not exist in v2 — Foundry IQ access is AAD-only via `AIProjectClient` ([ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)).

## Alternatives considered

1. **Keep Key Vault but use AAD-only retrieval** (Key Vault references in App Service `appsettings`). Rejected: keeps the cost (resource + RBAC + cold-start latency) without the benefit; the values being stored aren't actually secret.
2. **App Configuration with Key Vault references**. Rejected: same trade-off as above plus a second resource to provision; no need given the small, well-typed config surface.
3. **Use system-assigned managed identity instead of UAMI**. Rejected: SAMI lifecycle is bound to the host resource, which makes RBAC pre-provisioning awkward (the principal doesn't exist until the App Service exists). UAMI lets `infra/main.bicep` assign roles before any compute resource is created, eliminating a deploy-order dependency.
4. **Workload identity federation (OIDC)** for everything. Rejected for now: federation shines for cross-tenant / cross-cloud scenarios CWYD doesn't have, and it doesn't change the Key Vault question.

## References

- [`v2/infra/main.bicep`](../../infra/main.bicep) — UAMI definition, role assignments, Bicep outputs.
- [`v2/src/providers/credentials/`](../../src/providers/credentials/) — `managed_identity` and `cli` providers.
- [`v2/src/shared/settings.py`](../../src/shared/settings.py) — `AppSettings` (every field maps to a Bicep output env var, no secrets).
- [`copilot-instructions.md` Hard Rule #7](../../../.github/copilot-instructions.md) — bans Key Vault for app secrets in v2.
- [`development_plan.md` §2.1](../development_plan.md#21-removals) — removal entry; §3.6.2 — PostgreSQL Entra-ID guard.
- MACAE no-Key-Vault pattern: <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>.
- Azure Well-Architected Framework — Identity & Access Management: <https://learn.microsoft.com/azure/well-architected/security/identity-access>.
