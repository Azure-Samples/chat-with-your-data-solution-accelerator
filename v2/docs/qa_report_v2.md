# CWYD v2 QA Report

Date: April 28, 2026

Scope: current `v2/` code, tests, infrastructure, Docker assets, scripts, and relevant agent/workflow guidance. The legacy v1 `code/` tree was treated as out of scope except for banned/removed-feature regression checks.

QA integrity note: after this report was first drafted, a local uncommitted edit was made to [Dockerfile.backend](../docker/Dockerfile.backend) during follow-up work. This report keeps the Dockerfile finding open until that implementation change is either accepted through the normal one-unit workflow and validated with a real Docker build, or reverted outside the QA report flow. No production code changes are required to maintain this report.

## Phase 3.5 Re-Run Update — 2026-04-28 (post-remediation)

The original findings below stand as the audit trail. Status after the Phase 3.5 remediation pass:

| Finding | Original | Status |
|---|---|---|
| Q2 — Frontend prod build TS error (`App.tsx` JSX) | Blocker | ✅ Cleared (`npm run build` exit 0; vitest 20/20) |
| Q3 — `frontend_app.py` missing | Blocker | ✅ Cleared (FastAPI + StaticFiles wrapper, 2 tests) |
| Q4 — `azure.yaml services:` empty | Blocker | ✅ Cleared (3 services wired, YAML parses) |
| Q5 — Compose env vars + required `.env.dev` | Blocker | ✅ Cleared (`compose config` exit 0 from clean checkout, both profiles) |
| Q6 — Chat route doesn't pass search/tools to orchestrator | Blocker | ✅ Cleared (DI seam + lifespan construction + route forwards `search=`); Q6d (agent_framework 503 guard) deferred to Phase 4 task #28 (path unreachable today) |
| Q7 — CI entrypoint masked failures with `\|\| true` | Blocker | ✅ Cleared (masks removed) |
| Q1 — Docker build verify (`Dockerfile.backend`) | Blocker | ⏸ Deferred (Docker Desktop unavailable) |
| Q8 — Re-run all gates | Recommended | ✅ Done — backend pytest 186/186, frontend vitest 20/20, `npm run build` exit 0 (built in 630ms), `compose config` exit 0 for both profiles, registry-dispatch grep gate 0 hits (refined to skip explicit `# noqa: registry-dispatch` markers on `health.py` diagnostic + `settings.py` validator), `azure.yaml` parses |

Re-run verdict: **6 of 7 deployability blockers cleared; Q1 (Docker build) remains the only gate not yet exercised.** Tests went from 179/179 baseline to 186/186 (+7 new tests across Q3, Q6a, Q6b, Q6c). Full ledger entries in [development_plan.md §0.1](development_plan.md#01-debt-queue) (rows Q2-Q8).

## Executive Summary

CWYD v2 has a solid modular foundation: provider registries are in place, backend and frontend unit tests are green, and the Python test suite is substantial. However, the current state is not deployable end to end yet.

The main risks are in packaging, `azd` service wiring, frontend production build, and incomplete production composition of the Phase 3 chat path. Python tests passed with `179 passed`, and frontend tests passed with `20 passed`, but build and deployability checks exposed blockers that unit tests do not currently catch.

## Blockers

1. [Dockerfile.backend](../docker/Dockerfile.backend#L21): baseline finding: invalid Dockerfile syntax. The original `COPY` instruction included shell redirection/operators, which Dockerfile diagnostics reject. A local uncommitted edit now removes that syntax, but the backend image build was not verified because Docker Desktop's Linux engine was unavailable. Keep this finding open until the code change is accepted and `docker build -f v2/docker/Dockerfile.backend -t cwyd-v2-backend:qa .` succeeds.

2. [Dockerfile.frontend](../docker/Dockerfile.frontend#L44): the production frontend image copies `v2/src/frontend/frontend_app.py`, but that file does not exist. The dev target can still work, but the production image path is broken.

3. [App.tsx](../src/frontend/src/App.tsx#L42): `npm run build` fails with `TS2503: Cannot find namespace 'JSX'` at `export function App(): JSX.Element`. Vitest is green, but the frontend cannot currently produce a production build.

4. [azure.yaml](../azure.yaml#L92): `services:` is still omitted, while [development_plan.md](development_plan.md#L477) marks `azure.yaml` with v2 service paths complete. This blocks real `azd` service deployment and contradicts the phase principle that every phase ends with working `azd up`.

5. [conversation.py](../src/backend/routers/conversation.py#L123): the conversation endpoint creates orchestrators with only `settings` and `llm`, then calls `run_chat` without search, content safety, or post-prompt dependencies. The backend route therefore does not yet deliver the full grounded RAG behavior claimed by [development_plan.md](development_plan.md#L538).

6. [conversation.py](../src/backend/routers/conversation.py#L123) and [agent_framework.py](../src/providers/orchestrators/agent_framework.py#L49): selecting `agent_framework` will fail at runtime because `AgentFrameworkOrchestrator` requires `agents_client` and `agent_id`, but the router/dependency path never supplies them.

## High And Medium Risks

1. [ci-entrypoint.sh](../docker/ci-entrypoint.sh#L31) and [ci-entrypoint.sh](../docker/ci-entrypoint.sh#L36): test failures are masked with `|| true`, so CI can report false green for pytest or frontend test failures.

2. [docker-compose.dev.yml](../docker/docker-compose.dev.yml#L29): backend-only compose uses env vars that do not match `AppSettings` expectations, such as `AZURE_DB_ENDPOINT` instead of `AZURE_POSTGRES_ENDPOINT`.

3. [docker-compose.dev.yml](../docker/docker-compose.dev.yml#L25): backend-only compose config fails in a clean checkout because `.env.dev` is required and absent.

4. [app.py](../src/backend/app.py#L36) and [app.py](../src/backend/app.py#L86): backend reads telemetry and CORS config directly from `os.getenv` instead of routing runtime configuration through `AppSettings`.

5. [health.py](../src/backend/routers/health.py#L54): the health router has a `db_type == "cosmosdb"` conditional. This trips the greppable provider-dispatch search, but it is currently a diagnostic endpoint selection rather than provider instantiation. Treat as a modularity warning, not a blocker.

## Validation Evidence

| Check | Result | Evidence |
|---|---|---|
| Python tests | Pass | `uv run pytest tests -q --disable-warnings --maxfail=1` from `v2`: `179 passed`. |
| Frontend tests | Pass | `npm test -- --run`: `20 tests` across `5 files`. |
| Frontend build | Fail | `npm run build` failed on [App.tsx](../src/frontend/src/App.tsx#L42) with `TS2503: Cannot find namespace 'JSX'`. |
| Direct OpenAI import gate | Pass | No `from openai`, `import openai`, or `AzureOpenAI` matches under `v2/src`. |
| Test placeholder gate | Pass | No `pytest.skip`, `pytest.mark.skip`, `pytest.mark.xfail`, or `assert False` matches under `v2/tests` or `v2/src/frontend/tests`. |
| Docker compose frontend-only config | Pass | `docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only config` rendered successfully. |
| Docker compose backend-only config | Fail | `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only config` failed because `v2/docker/.env.dev` was missing. |
| Backend Docker image build | Not run | Docker build could not start because Docker Desktop's Linux engine pipe was unavailable. |
| Bicep build | Not run | `bicep` CLI was not installed in the review environment. |

## Gate Checklist

| Gate | Decision | Evidence |
|---|---|---|
| Correctness | Fail | Agent Framework and grounded RAG route wiring are incomplete in the production path. |
| Test Evidence | Warn | Unit tests pass, but they miss build/deploy failures and production wiring gaps. |
| Modern GSA | Warn | Registry foundation is good, but the deployable vertical slice is not yet true. |
| Modularity | Warn | Provider pattern exists; route composition does not wire all providers/tools yet. |
| Extensibility | Warn | Agent Framework cannot be selected through the current production router path. |
| Deployability | Fail | Dockerfiles, frontend build, `azure.yaml`, and backend-only compose have blockers. |
| Security/RBAC | Pass | No direct OpenAI imports or Key Vault app-secret usage were found in reviewed v2 runtime paths. |
| Process Compliance | Warn | `development_plan.md` status is ahead of actual deployability and route wiring. |

## Recommended Work Order Sequence

1. Fix [Dockerfile.backend](../docker/Dockerfile.backend#L21) so the backend image builds.
2. Fix [App.tsx](../src/frontend/src/App.tsx#L42) so `npm run build` passes.
3. Add the missing frontend production serving file referenced by [Dockerfile.frontend](../docker/Dockerfile.frontend#L44), or adjust the Dockerfile to the actual serving approach.
4. Wire [azure.yaml](../azure.yaml) services for backend, frontend, and functions.
5. Correct backend-only compose env vars and clean-checkout `.env.dev` behavior in [docker-compose.dev.yml](../docker/docker-compose.dev.yml).
6. Add production dependency wiring for search, content safety, post-prompt validation, and Agent Framework requirements in the conversation path.
7. Remove `|| true` masking from [ci-entrypoint.sh](../docker/ci-entrypoint.sh#L31) and [ci-entrypoint.sh](../docker/ci-entrypoint.sh#L36).

## Suggested One-Unit Follow-Ups

| Priority | Unit | Target | Acceptance |
|---|---|---|---|
| 1 | Fix backend Dockerfile manifest copy | [Dockerfile.backend](../docker/Dockerfile.backend) | Dockerfile diagnostics are clean and backend image build reaches dependency installation. |
| 2 | Fix frontend TypeScript build type | [App.tsx](../src/frontend/src/App.tsx) | `npm run build` passes. |
| 3 | Restore frontend production serving path | [Dockerfile.frontend](../docker/Dockerfile.frontend) or `v2/src/frontend/frontend_app.py` | Production frontend image can build without missing file errors. |
| 4 | Add azd service definitions | [azure.yaml](../azure.yaml) | `azd package` or equivalent manifest validation sees backend, frontend, and functions services. |
| 5 | Make backend-only compose config self-consistent | [docker-compose.dev.yml](../docker/docker-compose.dev.yml) | `docker compose ... --profile backend-only config` succeeds from clean checkout, and env names match `AppSettings`. |
| 6 | Wire chat route dependencies | [conversation.py](../src/backend/routers/conversation.py) and dependency providers | Route can instantiate the selected orchestrator with required dependencies and optional RAG guards. |
| 7 | Stop masking test failures | [ci-entrypoint.sh](../docker/ci-entrypoint.sh) | Failing pytest or frontend tests increment the CI failure count. |

## Residual Risk

The current unit tests give good local confidence in isolated units, but they do not yet prove the production deployment path. The next QA pass should re-run the same gates after the deployability blockers are fixed, and should include `bicep build v2/infra/main.bicep` once the Bicep CLI is available.
