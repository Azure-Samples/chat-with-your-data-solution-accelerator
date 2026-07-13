# ADR 0006 — Split `/api/health` (always 200) from `/api/health/ready` (503 on fail)

- **Status**: Accepted
- **Date**: 2026-04-26
- **Phase**: 2 (post-build review fix; refines task #13)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

The first cut of the health router shipped a single endpoint:

```
GET /api/health  →  200 OK with body { status, version, checks: [...] }
```

The body's `status` field encoded severity (`pass` / `fail` / `degraded`), but the HTTP status code was always 200. That collapsed two distinct consumers into one endpoint:

1. **Operators / dashboards** want a *diagnostic* read — "tell me what's up and what's broken." A non-200 here is hostile: it makes the dashboard go red even when the deployment is intentionally in a partial mode (e.g., pgvector instead of Azure Search), and it makes `curl` exit non-zero in shell pipelines we'd rather not babysit.
2. **Kubernetes / Azure Container Apps readiness probes** want a *binary* signal — "should the load balancer route traffic to this replica?" A 200-always endpoint is useless for this. The orchestrator needs a non-2xx to take the pod out of rotation.

We also shipped a bug: the aggregation rule treated `skip` as severity-bearing and demoted overall status to `degraded` whenever any check returned `skip`. That permanently advertises pgvector deployments as degraded — `search` is *legitimately* not present in that mode, not broken.

Both issues surfaced in the post-build review (drifts D2 and D3). This ADR locks the resolution.

## Decision

**Split the endpoint into two, each with a single, clear consumer contract.**

### `GET /api/health` — diagnostic, always 200

```http
GET /api/health
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "pass" | "fail",
  "version": "v2",
  "checks": [
    {"name": "foundry_iq", "status": "pass" | "fail" | "skip", "detail": "..."},
    {"name": "database",   "status": "pass" | "fail" | "skip", "detail": "..."},
    {"name": "search",     "status": "pass" | "fail" | "skip", "detail": "..."}
  ]
}
```

- **Always 200**, regardless of body. Operators and dashboards consume the body.
- Body is the *full* check report so a single curl tells you what's wrong.

### `GET /api/health/ready` — readiness probe, 503 on fail

```http
GET /api/health/ready
HTTP/1.1 200 OK    (when status == "pass")
HTTP/1.1 503 Service Unavailable    (when status == "fail")
```

- Same body shape as `/api/health`.
- Status code carries the binary signal Kubernetes / ACA need.

### Aggregation rule

`_aggregate(checks)` returns only `"pass"` or `"fail"`:

```python
def _aggregate(checks: list[DependencyCheck]) -> Literal["pass", "fail"]:
    if any(c.status == "fail" for c in checks):
        return "fail"
    return "pass"   # `skip` is neutral; `pass` only counts as "pass"
```

`skip` is **neutral**. It means "this dependency does not exist in this deployment mode by design" (e.g., `search` is `skip` when `index_store=pgvector`). It does not influence overall status.

`degraded` is reserved as a **future** value for optional-check failures (e.g., a non-blocking telemetry exporter being down). Today no check returns `degraded`; the comment in the source documents the reservation.

### Per-check `status` values

| Value | Meaning | Effect on overall |
|---|---|---|
| `pass` | Dependency configured + reachable (shallow). | Counts as pass. |
| `fail` | Dependency configured but unreachable / misconfigured. | Demotes overall to `fail`. |
| `skip` | Dependency intentionally absent in this deployment mode. | Neutral. |

### Probe depth

Both endpoints currently do **shallow** probes — env-var presence + DI wire-up only. Deep probes (`HEAD` against Foundry, `GET` against Search index, SQL `SELECT 1`) are explicitly deferred to Phase 6 (`development_plan.md` task #13 deferral). The split-endpoint contract above does not change when depth is added; only the per-check `_check_*` helper bodies do.

## Consequences

### Positive

- **Operators get a diagnostic that always returns 200.** Dashboards stay green when intent matches reality; the body explains what's degraded when it isn't.
- **K8s / ACA get the 5xx they need.** A failing readiness probe takes the pod out of rotation immediately. No custom controller needed.
- **pgvector deployments stop reporting "degraded" forever.** `skip` is neutral, so `search=skip` + `database=pass` + `foundry_iq=pass` aggregates to `pass`.
- **Future-proof**: `degraded` is reserved but unused, so adding optional checks later (e.g., `app_insights_export`) doesn't require an aggregation-rule change — the `_aggregate` body just adds `if any(c.status == "degraded" ...): return "degraded"` on top.
- **Two endpoints, two tests.** Clear what to assert: `/api/health` is always 200; `/api/health/ready` is 200 on pass and 503 on fail.

### Negative

- **Two endpoints to discover.** A new contributor reading the router sees both and must figure out which to consume. Mitigated by the docstring on each handler stating the consumer.
- **Slight duplication**: both handlers call the same `_run_checks(settings)` helper. We accept it — DRYing further would only obscure the contract.
- **`/api/health/ready` returns 503 by mutating `Response.status_code`** inside the handler (FastAPI pattern), not via `HTTPException`. Worth knowing but routine.

### Neutral

- **No `/livez` endpoint.** A liveness probe asks "is the process up?" — for a FastAPI app, "the request returned at all" already answers that. Adding `/livez` would be cargo-culted from K8s docs without a real signal to encode. Revisit if we ever block the event loop on something that could deadlock without dying.

## Alternatives considered

1. **Keep one endpoint, return 503 in the body when severity is `fail`, leave HTTP 200.** Rejected: this is what we had; doesn't satisfy the K8s probe consumer.
2. **One endpoint, set HTTP status from severity** (200 / 503 / 503). Rejected: hostile to dashboards. A single curl-and-grep tool can't easily distinguish "intentionally partial" from "broken" if both produce 5xx.
3. **Two endpoints, but `/api/health/ready` returns 200 even on fail with a body field.** Rejected: defeats the purpose of having a separate readiness endpoint.
4. **Use `fastapi-health` or another community plugin.** Rejected: 30 lines of router code don't justify a dependency, and the plugins we surveyed bake in opinions (severity hierarchy, retry policy) we'd want to override anyway.
5. **Per-dependency endpoints** (`/api/health/foundry`, `/api/health/database`). Rejected: cardinality explodes when we add Phase 3+ dependencies, and operators want one view, not N.

## References

- [`v2/src/backend/routers/health.py`](../../src/backend/routers/health.py) — both endpoints + shared `_run_checks` helper + `_aggregate` rule.
- [`v2/src/backend/models/health.py`](../../src/backend/models/health.py) — `HealthResponse`, `DependencyCheck`.
- [`v2/tests/backend/test_health.py`](../../tests/backend/test_health.py) — 5 tests for `/api/health` (including `skip-is-neutral`), 2 tests for `/api/health/ready` (200 + 503).
- [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md) — the DI shape the health router consumes.
- [`development_plan.md` §0 + Phase 2 task #13](../development_plan.md) — task and review-fix entry.
- Kubernetes probes: <https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/>.
- Azure Container Apps health probes: <https://learn.microsoft.com/azure/container-apps/health-probes>.
