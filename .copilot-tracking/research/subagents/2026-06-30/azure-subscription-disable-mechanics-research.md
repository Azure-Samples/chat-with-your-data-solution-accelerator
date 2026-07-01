<!-- markdownlint-disable-file -->
# Research: Azure Subscription Disable Mechanics (`CSA-CTO-Engineering-Dev` going read-only overnight)

Status: Complete (high confidence on Q1, Q2, Q3, Q5, Q6, Q7; Q4 answered with documented cadence mechanics; the specific automation that fires nightly on THIS subscription can only be confirmed by running the disambiguating checks in the Q5 section against the live sub)

## Research Topics / Questions

1. Azure subscription lifecycle states (`Enabled`, `Warned`, `PastDue`, `Disabled`, `Expired`, `Deleted`) — meanings, which block writes, transition sequence + timing.
2. Causes of `ReadOnlyDisabledSubscription` — enumerate distinct mechanisms and how each manifests in `state`.
3. What the platform does to resources after disable (deallocate → stop billing → delete after retention). Does deletion emit activity-log `delete` events?
4. Recurring/daily disable behavior on credit/spending-limit subs.
5. Exact read-only diagnostics (portal + `az` CLI).
6. Reactivation per disable type; "Remove spending limit" mechanics.
7. Best-practice guidance for credit/budget-capped shared dev subscriptions.

## Observed Signature (this session)

- `az account list --all --refresh` → subscription state `Warned` (NOT `Enabled`).
- Write probe (`az tag update --operation merge`) → HTTP 409 `ReadOnlyDisabledSubscription`.
- Overnight activity log: ~300 events, almost all `Microsoft.Resources/deployments/write` + role-assignment writes (yesterday's provisioning) + governance policy actions (`auditIfNotExists/action`, `deployIfNotExists/action`). ZERO `…/delete` events.
- All resources in the RG are gone despite zero delete events.
- Pattern repeats "every morning."

---

## Findings

### Q1 — Subscription lifecycle states: meanings, which block writes, transition + timing

Source: [Azure subscription states](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states) (Microsoft Cost Management).

The portal/CLI `Status`/`state` field maps to these states. Each state's allowed ARM operations:

| State | Meaning | Writes (PUT/PATCH/POST) | Reads/Delete (GET/DELETE) | Billed? |
| --- | --- | --- | --- | --- |
| **Active / Enabled** | Normal. Deploy + manage. | Allowed (all of PUT/PATCH/DELETE/POST/GET) | Yes | Yes |
| **Warned** | Warning state; if unaddressed it becomes **Disabled**. Entered when the sub is **past due, canceled by a user, or expired**. | **Blocked** (PUT/PATCH/POST) | GET/DELETE only | **No — "isn't charged."** |
| **Past Due** | Outstanding payment pending. Sub is **still active**; non-payment may lead to disable. | **All operations available** | Yes | Yes |
| **Disabled** | Cannot create/manage. VMs deallocated, temp IPs freed, **storage read-only**, services disabled. | Blocked (PUT/PATCH + POST) | GET/DELETE; transfer-ownership disabled | No |
| **Expired** | Sub was **canceled**; reactivatable. | Blocked (PUT/PATCH + POST) | GET/DELETE | No |
| **Deleted** | Sub + all underlying resources/data deleted. | No operations | None | No |

Key quotes:
- **Warned**: "If the warning isn't addressed, the subscription gets disabled. A subscription might be in warned state if its past due, canceled by a user, or if the subscription expired. You can retrieve or delete resources (GET/DELETE), but you can't create any resources (PUT/PATCH/POST). **Resources in this state go offline but can be recovered when the subscription resumes an active/enabled state.** A subscription in this state isn't charged."
- **Disabled**: "A subscription can get disabled because of the following reasons: Your credit expired. You reached your spending limit. Your bill is past due. Your credit card limit was exceeded. Or, it was explicitly disabled or canceled. Depending on the subscription type, a subscription might remain disabled between **1 - 90 days. After which, it gets permanently deleted.**"

**Transition sequence + timing.** Documented general flow for billing/lifecycle disablement:
- `Enabled` → (payment problem) → `PastDue` (still fully writable) → `Warned` (writes blocked, not billed, resources offline-but-recoverable) → `Disabled` (writes blocked, resources deallocated) → permanently `Deleted` after a **1–90 day** retention window (varies by subscription type). For a **canceled** sub: cancel → `Expired`/`Warned` → auto-`Deleted` ~90 days later (see Q3).
- Exact dwell time in `Warned` before `Disabled` is not published as a fixed number; it's "if the warning isn't addressed." For organic billing reasons it's typically days. **A sub that is `Warned` every morning and writable again later is not the organic billing path** — it indicates an external scheduled flip (see root-cause analysis).

Note on the REST enum vs the docs: the [Subscriptions - Get REST API](https://learn.microsoft.com/en-us/rest/api/resources/subscriptions/get) `SubscriptionState` enum lists only `Enabled, Warned, PastDue, Disabled, Deleted` (no `Expired` in the API enum — "Expired" is a portal-facing label for a canceled sub).

### Q2 — Causes of `ReadOnlyDisabledSubscription`, by mechanism + how each manifests in `state`

The 409 `ReadOnlyDisabledSubscription` is the ARM write-plane refusal that fires whenever the subscription is **not** in `Enabled`/`PastDue` (i.e., it is `Warned`, `Disabled`, or `Expired`). Distinct mechanisms that drive a sub into those states:

| # | Mechanism | What it is | Typical `state` | Auto-reactivates? |
| --- | --- | --- | --- | --- |
| **(a)** | **Spending limit reached** (credit offers: Free Trial, MSDN/Visual Studio, Azure Pass, Azure in Open, Azure for Students; multi-month-credit VS Enterprise/Professional) | Usage exhausts included monthly credit → Azure disables deployed services for the **rest of that billing period**. | `Disabled` (+ "spending limit reached / remove spending limit" banner) | **Yes** — multi-month-credit offers "re-enabled automatically at the beginning of the next billing period." (Monthly cadence.) |
| **(b)** | **Cost Management budget with an automated action** | A budget (sub/RG scope) wired to an **action group** that invokes automation (Logic App → Automation runbook / Function / webhook). The action can stop VMs, **or cancel/disable the subscription**. Budgets evaluated **every ~24 hours**. | Stop-VMs leaves `Enabled`; a cancel/disable action drives `Warned`/`Disabled`/`Expired`. | Only if the automation (or a paired re-enable job) flips it back. **Cadence can be daily.** |
| **(c)** | **Azure Policy / governance automation** | Policy (`audit/deny/deployIfNotExists/auditIfNotExists`) **cannot disable a subscription**. But governance *tooling* (scheduled/policy-state-triggered runbook/Logic App/Function) can call the cancel/disable API. The policy `…/action` events seen are governance side-effects, **not** the disabler. | Policy actions don't change `state`; paired automation does. | Per the automation's schedule. |
| **(d)** | **Admin- or automation-initiated disable/cancel** | A subscription Owner (human) or service principal/automation calls `az account subscription cancel` / cancel REST API (or an internal cost-governance system disables non-prod subs on a schedule). | `Warned` then `Expired`/`Disabled` (cancel path) | Manual `Reactivate`, or a paired nightly re-enable automation. |
| **(e)** | **Payment / past due / card limit** | Unpaid invoice or exceeded card limit. | `PastDue` (still writable) → `Warned` → `Disabled` | After payment + up to 24h. (Not a nightly pattern.) |

Sources: [subscription-disabled](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-disabled), [spending-limit](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit), [cost-management-budget-scenario](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cost-management-budget-scenario), [tutorial-acm-create-budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets), [subscription-states](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states).

Important clarifier on the error text: the 409 message says "disabled … marked as read only … until it is re-enabled" even when `az account list` reports the literal state as **`Warned`**. `Warned` already blocks writes (Q1), so the ARM write plane reports it with the same `ReadOnlyDisabledSubscription` code — i.e., **the error does not by itself distinguish `Warned` from `Disabled`**.

### Q3 — What the platform does to resources after disable; do deletions emit activity-log events?

Sources: [subscription-states](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states), [spending-limit](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit), [cancel-azure-subscription](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cancel-azure-subscription), [avoid-unused-subscriptions](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/avoid-unused-subscriptions).

Staged platform behavior on disable:
1. **Take resources offline / deallocate (immediate).** Spending-limit: "Azure resources … are **removed from production** and your Azure virtual machines are **stopped and de-allocated**. The data in your storage accounts are available as **read-only**." Disabled: "VMs are deallocated, temporary IP addresses are freed, storage is read-only and other services are disabled." **Warned**: "**Resources in this state go offline but can be recovered when the subscription resumes an active/enabled state.**"
2. **Stop billing.** `Warned` "isn't charged"; cancel "billing is stopped immediately."
3. **Permanent deletion after a retention window.** Disabled: "might remain disabled between **1 – 90 days. After which, it gets permanently deleted.**" Cancel: "Microsoft waits **30 to 90 days** before permanently deleting your data"; "automatically deleted **90 days** after you cancel." Inactivity: blocked → "**deleted in 90 days**" with "Any resources in the subscription are also deleted."

**Do the takedown/deletion emit activity-log `…/delete` events? No — this is the key to the zero-delete observation.** "Resources go offline / removed from production / deallocated" when a subscription is `Warned`/`Disabled` is a **billing-plane / platform-internal state change against the whole subscription**, not a sequence of per-resource ARM `DELETE` operations. The Activity Log records ARM control-plane operations against resources (e.g., `Microsoft.Compute/virtualMachines/delete`); a subscription-wide disable that takes resources offline does **not** generate one `…/delete` event per resource. In `Warned` the resources are explicitly **offline-but-recoverable** (not deleted — they return when the sub goes `Enabled`). So: **resources "gone" from the portal/`az resource list` + ZERO `…/delete` activity-log events is the exact, documented fingerprint of a billing-plane subscription disable (Warned/Disabled), not a delete-issuing cleanup job.**

Corroborating: Cost Management notes data "includes resources, resource groups, and subscriptions that might be stopped, deleted, or canceled … it might not match … Azure Resource Manager or Azure Resource Graph, as they only display currently deployed resources" — i.e., ARM/ARG stop showing offline resources without a delete trail.

### Q4 — How a credit/budget-capped sub behaves recurringly; how a disable can appear "every morning"

- **Pure spending-limit (credit) exhaustion is MONTHLY, not daily.** "When your usage reaches the spending limit, Azure disables your subscription **for the rest of that billing period**" and "re-enabled automatically at the beginning of the next billing period." So organic credit exhaustion disables once per billing period and re-enables at the period boundary — it does **not** produce a clean nightly Warned→Enabled cycle.
- **Budgets are evaluated every ~24 hours** ("evaluated against these costs **every 24 hours**"; cost data available within 8–24h). A **daily-reset budget** (or a budget whose action runs on each evaluation) wired to a **disable/cancel action group** can flip the sub read-only on a daily cadence.
- **Three plausible ways the disable appears "every morning":**
  1. **A scheduled governance automation** (nightly Automation runbook / Logic App / Function, or an internal cost-governance system) that **cancels/disables non-prod subscriptions overnight** and (optionally) re-enables them after a window — produces `Warned` overnight, recoverable by re-enable. **Best fit for the observed signature.**
  2. **A Cost Management budget + action group** that triggers a disable when a (small/daily) threshold is crossed each evaluation cycle.
  3. **Daily credit exhaustion** only if there is a paired nightly re-enable automation AND always-on resources burn the daily slice of credit each day — possible but least clean, and it would normally surface as `Disabled` + a spending-limit banner rather than `Warned`.

### Q5 — Exact read-only diagnostics (work while the sub is `Warned`/read-only)

All of these are **GET/read operations**, which remain allowed in `Warned`/`Disabled`/`Expired` (Q1).

**Single most decisive CLI check — read offer (quotaId) + spending limit + state in one call:**
```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>?api-version=2022-12-01" \
  --query "{name:displayName, state:state, quotaId:subscriptionPolicies.quotaId, spendingLimit:subscriptionPolicies.spendingLimit}" -o jsonc
```
Returns `state` (`Enabled|Warned|PastDue|Disabled|Deleted`), `subscriptionPolicies.quotaId` (the **offer fingerprint**), and `subscriptionPolicies.spendingLimit` (`On|Off|CurrentPeriodOff`). Confirmed by the [Subscriptions - Get REST API](https://learn.microsoft.com/en-us/rest/api/resources/subscriptions/get) (response includes `subscriptionPolicies.{quotaId, spendingLimit, locationPlacementId}`; the doc's own sample shows `"quotaId": "Internal_2014-09-01", "spendingLimit": "Off"`). `az account subscription show --id <SUBSCRIPTION_ID>` (account extension, experimental) returns the same `subscriptionPolicies` block.

**Map `quotaId` → offer type** (from [understand-cost-mgt-data → Supported offers](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data)):

| quotaId | Offer | Spending-limit capable? |
| --- | --- | --- |
| `FreeTrial_2014-09-01` | Free Trial (MS-AZR-0044P) | Yes (credit) |
| `MSDN_2014-09-01` | MSDN / Visual Studio Enterprise/Professional (0062P/0063P/0059P) | Yes (multi-month credit) |
| `MSDNDevTest_2014-09-01` | Enterprise/PAYG Dev/Test, VS Test Pro (0148P/0023P/0060P) | Varies |
| `Sponsored_2016-01-01` | Microsoft Azure Sponsorship (MS-AZR-0036P) | Credit-capped |
| `AzurePass_2014-09-01` | Azure Pass (0120P…) | Yes (credit) |
| `PayAsYouGo_2014-09-01` | Pay-as-you-go (MS-AZR-0003P) | **No** spending limit |
| `EnterpriseAgreement_2014-09-01` | EA / Microsoft Azure Plan (MCA) (0017P/0017G) | **No** spending limit |
| `Internal_2014-09-01` | **Microsoft internal subscription** | Governed by internal cost automation |

Decision rule from this one call:
- `spendingLimit = On` (and a credit quotaId) → spending-limit class is in play (monthly cadence; a nightly recovery would require external re-enable automation).
- `spendingLimit = Off`/`CurrentPeriodOff` with `EnterpriseAgreement`/`PayAsYouGo`/`Internal` quotaId → **spending-limit credit exhaustion is impossible**; the nightly read-only flip is therefore necessarily caused by **external automation** (budget action group or a governance/cost runbook). For a sub named `CSA-CTO-Engineering-Dev`, an `Internal_*` quotaId is the likely result, pointing at internal cost-governance automation.

**Other read-only CLI checks:**
```bash
# State across all subs (what you already ran):
az account list --all --refresh -o table

# Budgets on the sub (look for any with a notification wired to a contactGroups/action group):
az consumption budget list --subscription <SUBSCRIPTION_ID> -o jsonc
#   action groups appear under notifications[].contactGroups[] (resource IDs of microsoft.insights/actionGroups)

# Inspect any action group the budget points at (Logic App / runbook / webhook / function?):
az monitor action-group show --ids <ACTION_GROUP_RESOURCE_ID> -o jsonc

# Policy assignments (confirm the auditIfNotExists/deployIfNotExists you saw are governance, not the disabler):
az policy assignment list --subscription <SUBSCRIPTION_ID> -o table

# Activity log around the nightly flip — Administrative ops; look for a subscription cancel/enable
# or an action-group / Logic App / runbook invocation near the disable timestamp:
az monitor activity-log list \
  --subscription <SUBSCRIPTION_ID> \
  --offset 18h --max-events 1000 \
  --query "[?category.value=='Administrative'].{time:eventTimestamp, op:operationName.value, by:caller, status:status.value}" -o table
```
Note: `az consumption budget list`, `az policy assignment list`, `az monitor activity-log list`, and the subscription GET are all **read operations** and succeed on a `Warned`/read-only sub. Anything that writes (`az tag update`, `az group create`, `az account subscription enable`) will 409 until re-enabled.

**Portal (read-only navigation):**
- **Subscription → Overview**: the top **banner** states the reason ("disabled because you reached your spending limit / payment wasn't received / it was canceled"). Fastest human-readable cause.
- **Subscription → Overview → Properties** (or JSON view): shows **Offer / quota id** and **Spending limit On/Off**.
- **Cost Management + Billing → Cost Management → Budgets** (scope = the sub): check budget, threshold, **reset period** (Monthly vs Billing month), and whether a **notification is wired to an action group**; open that action group to see if it triggers a Logic App / Automation runbook / Function / webhook.
- **Cost Management + Billing → Subscription → Spending limit**: whether On and reached this period.
- **Monitor → Activity log** (filter Administrative, overnight timespan): the operation that changed state + the **caller** (human Owner vs service principal/automation).
- **Subscription → Overview → "Reactivate"** (Owner only) appears for canceled/disabled subs.

### Q6 — Reactivation per disable type; "Remove spending limit" mechanics

Source: [subscription-disabled](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-disabled), [spending-limit](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit), [az account subscription](https://learn.microsoft.com/en-us/cli/azure/account/subscription).

| Disable type | Reactivation |
| --- | --- |
| **Spending limit reached** (multi-month credit) | **Automatic** at next billing period. To use now: **Remove the spending limit** (needs valid payment method) or upgrade (Free Trial → PAYG). |
| **Credit expired** (Free Trial 30-day) | **Upgrade** the subscription to PAYG. |
| **Past due / card limit** | Settle balance / switch card / switch to invoice. **Up to 24h** to reactivate after payment. |
| **Canceled (by Owner/Account Admin)** | **Subscription → Reactivate** (PAYG self-service). Non-PAYG: contact support within **90 days**. |
| **Admin/automation disable** | Owner re-enables (`az account subscription enable --subscription-id <id>`, account extension, experimental), or the governance automation re-enables on its schedule. |
| **Blocked for inactivity** | Create a support request to unblock (else deleted after 90 days). |

Post-reactivation: "there might be a delay in creating or managing resources … Most Azure resources automatically resume" (check/restart services; contact billing support if >30 min).

**"Remove spending limit"** ([spending-limit#remove](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit)):
- Available **only** for offers that have a spending limit (Free Trial, VS/MSDN credit offers). **Not available** for PAYG, EA, or commitment-plan subs (no limit to remove).
- **Prerequisites/permissions**: sign in as **Account Administrator**; a **valid payment method** must be attached. Steps: Cost Management + Billing → select sub → Overview banner → "Remove spending limit" → choose **"Remove indefinitely"** (won't auto-re-enable next period; can turn back on) **or** "**Remove for current billing period only**" (auto re-enables next period) → select payment method → Finish.
- Direct deep link if banner missing: `https://portal.azure.com/#blade/Microsoft_Azure_Billing/RemoveSpendingLimitBlade/subscriptionId/<SUBSCRIPTION_ID>`.
- Free Trial caveat: removing the limit converts the Free Trial to individual PAYG at the end of the trial.

### Q7 — Best practices for a credit/budget-capped shared dev subscription

Synthesis of Microsoft guidance ([spending-limit](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit), [tutorial-acm-create-budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets), [cost-management-budget-scenario](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cost-management-budget-scenario), [cancel-azure-subscription "prevent unwanted charges"](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cancel-azure-subscription)):

- **Treat the dev sub as ephemeral.** Microsoft's default budget guidance is explicit: alert-only budgets "**don't affect** resources and your consumption isn't stopped." Prefer **alert-only budgets** (multiple thresholds → email/Teams) over budgets wired to **disable/stop** action groups, so work isn't blocked.
- **Tear down nightly, redeploy on demand.** Because a disable takes resources offline without a delete trail, design every dev deployment to be **fully `azd up`/IaC re-creatable each morning** (idempotent Bicep/Terraform). Don't keep state you can't recreate on a sub that flips read-only nightly. (Matches this repo's azd-only, ephemeral posture.)
- **Avoid always-on/credit-burning resources on credit subs.** The spending-limit doc warns specific items (third-party images like Oracle, Azure DevOps Services, Microsoft Entra ID P1/P2, support plans, most Marketplace branded services) "**can't be used with subscription credits**" and "cause your subscription to be disabled" almost immediately. Keep these off a credit-capped dev sub; **stop/deallocate VMs and delete idle resources** at end of day to preserve credit.
- **If a hard cap is required, scope the automation to stop resources, not cancel the subscription.** The budget-automation tutorial's reference pattern **stops VMs in a resource group** at 80%/100% — it leaves the subscription `Enabled`. A cancel/disable action is heavier and blocks all writes; prefer stop-resources orchestration if a budget action is mandated.
- **Move anything that must stay up to PAYG/EA.** Persistent workloads belong on a **pay-as-you-go or EA** sub (no spending limit; `spendingLimit = Off`) so they aren't deallocated when a credit period closes.
- **Find and fix the actual nightly trigger.** For THIS sub, the fastest unblock is to identify the automation (per Q5: budget action group, governance runbook, or internal cost system) and either exclude the working RG, switch the budget to alert-only, or get the owning team to stop the nightly disable — rather than re-enabling manually each morning.

---

## Most-likely root cause (given the observed signature)

**Signature recap:** `state = Warned` (not `Disabled`/`PastDue`/`Expired`), 409 `ReadOnlyDisabledSubscription` on write, **zero `…/delete` activity-log events** yet RG resources gone, **recurs every morning**, on a **named shared engineering dev** subscription.

**Conclusion (high confidence — the *class* of cause):** This is a **billing-plane subscription disable that takes resources offline at the platform level**, NOT a delete-issuing cleanup job. The `Warned` state doc is the exact match: writes blocked (→ `ReadOnlyDisabledSubscription`), "**resources … go offline but can be recovered when the subscription resumes an active/enabled state**," and "isn't charged." A subscription-wide offline/deallocate does not emit per-resource ARM `DELETE` events — hence **zero delete events while resources vanish** is the textbook fingerprint of disable, not deletion. (Confidence: ~0.9.)

**Conclusion (moderate-high confidence — the *trigger*):** The **nightly, recover-by-morning** cadence is **not** organic credit/spending-limit exhaustion (that's monthly and surfaces as `Disabled` + a spending-limit banner, re-enabling at the billing-period boundary, not nightly). The clean `Warned`-overnight pattern on a shared internal-style dev sub points to an **external scheduled automation that cancels/disables the subscription on a nightly cost-governance cadence** (an org/internal cost-governance runbook/Logic App/Function, or a Cost Management budget wired to a disable action group evaluated ~daily), with the sub returning to `Enabled` after a window. The `auditIfNotExists`/`deployIfNotExists` policy `…/action` events you saw are **governance side-effects, not the disabler** (Azure Policy cannot disable a subscription). (Confidence the trigger is external scheduled automation rather than organic billing: ~0.7 — pending the single check below.)

**Single best disambiguating check:** Run the subscription GET and read **`subscriptionPolicies.spendingLimit` + `subscriptionPolicies.quotaId`**:
```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>?api-version=2022-12-01" \
  --query "{state:state, quotaId:subscriptionPolicies.quotaId, spendingLimit:subscriptionPolicies.spendingLimit}" -o jsonc
```
- If `spendingLimit = Off` with `quotaId` = `EnterpriseAgreement_*` / `PayAsYouGo_*` / `Internal_*` → **credit exhaustion is impossible**, proving the nightly flip is **external automation** → then inspect `az consumption budget list` (budget→action group) and the **Administrative** activity-log entries at the disable timestamp to name the exact runbook/Logic App/identity.
- If `spendingLimit = On` with a credit `quotaId` (`FreeTrial_*`/`MSDN_*`/`Sponsored_*`/`AzurePass_*`) → spending-limit class is plausible; reconcile the nightly (vs monthly) cadence — a daily recovery still implies a paired re-enable automation.

This one call splits the two top hypotheses; the activity-log Administrative filter + budget/action-group inspection then names the specific nightly mechanism.

---

## Recommended next research (not completed here)

- [ ] Run the Q5 disambiguating commands against the live `CSA-CTO-Engineering-Dev` sub to read `state`/`quotaId`/`spendingLimit`, list budgets + action groups, and pull the Administrative activity-log entry at the disable timestamp (identifies the exact caller/automation). Requires the real subscription ID — out of scope for read-only doc research; do not commit the ID (repo Hard Rule #18).
- [ ] If the trigger is an internal/org cost-governance system, confirm the owning team's documented schedule + opt-out/exclusion process (not on public Microsoft Learn).
- [ ] Confirm whether a subscription cancel/disable surfaces in the Activity Log under `Microsoft.Subscription`/Administrative for this tenant (tenant-config dependent) to set expectations for future timestamp triangulation.

## Clarifying questions

- Do you have the live subscription ID and Owner/Reader access to run the Q5 read-only checks (so the trigger can be named), or is this purely an "explain the mechanism" request? (No code/commands were run this session — research is doc-only.)
- Is `CSA-CTO-Engineering-Dev` an internal Microsoft subscription (likely `Internal_*` quotaId) governed by a central cost-control system, or a customer/credit offer? That determines whether the fix is "ask the owning team to exclude your RG" vs "remove spending limit / move to PAYG."

## Sources

- Azure subscription states — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states
- Reactivate a disabled Azure subscription — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-disabled
- Azure spending limit (incl. remove/turn-on) — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit
- Cancel and delete your Azure subscription (retention 30–90 days, deallocate/read-only on cancel) — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cancel-azure-subscription
- Avoid charges with your Azure free account — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/avoid-charges-free-account
- Avoid unused subscriptions (inactivity block → delete in 90 days) — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/avoid-unused-subscriptions
- Azure billing and cost management budget scenario (budget → action group → Logic App/runbook orchestration) — https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/cost-management-budget-scenario
- Tutorial: Create and manage budgets (24h evaluation, alert-only "doesn't affect resources", action groups, CLI `az consumption budget`) — https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets
- Understand Cost Management data (quotaId↔offer table, ARM/ARG won't show offline resources) — https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data
- Subscriptions - Get REST API (subscriptionPolicies.quotaId/spendingLimit, SubscriptionState enum) — https://learn.microsoft.com/en-us/rest/api/resources/subscriptions/get
- az account subscription (CLI: show/enable/cancel, account extension) — https://learn.microsoft.com/en-us/cli/azure/account/subscription
