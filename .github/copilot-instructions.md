# Chat With Your Data (CWYD) — Repository Instructions

These instructions are **always loaded**. Read them before doing anything else.

## Repository layout (truth)

- `code/` — **v1 (legacy)**. Flask + Streamlit + Semantic Kernel + Prompt Flow + direct Azure OpenAI SDK. **Do not extend.** Only touch v1 to perform documented removals listed in [v2/docs/development_plan.md](../v2/docs/development_plan.md) §2.1.
- `v2/` — **v2 (active development)**. FastAPI + LangGraph + Agent Framework + Foundry IQ. All new work goes here.
- `infra/` (root) — v1 Bicep. v2 Bicep lives in `v2/infra/`.
- `tests/` (root) — v1 e2e/integration. v2 tests live under `v2/tests/` and `v2/src/**/tests/`.

## Mandatory references — consult before editing

1. [v2/docs/development_plan.md](../v2/docs/development_plan.md) — phase ordering, file paths, scope, removals, additions. Source of truth for **what** to build and **when**.
2. [v2/docs/pillars_of_development.md](../v2/docs/pillars_of_development.md) — every new core element must declare its pillar (Stable Core, Scenario Pack, Configuration Layer, or Customization Layer) in the file/class docstring.
3. Repo memory `cwyd-tech-stack.md` — current stack truth (versions, services, package managers).

## External pattern sources — read-only

You may **fetch and read** these for architectural patterns. **Never copy code wholesale** — adapt with attribution in a code comment when the pattern is non-trivial.

- Content Generation Solution Accelerator: <https://github.com/microsoft/content-generation-solution-accelerator>
- Multi-Agent Custom Automation Engine (MACAE): <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>

Specifically:

- MACAE → managed-identity + RBAC + no-Key-Vault env-var pattern; agent-to-agent message bus; SSE streaming pattern.
- CGSA → React/Vite + FastAPI plug-and-play surface; admin merged into frontend; reasoning visualization patterns.

## Hard rules

1. **One unit per turn.** Implement exactly **one class** OR **one method** per implementation turn. No "and while I'm here…" edits. Do not create multiple files of production code in a single turn unless they are a class + its test stub.
2. **Test-first contract.** Every new method/class lands with at least a `pytest` (Python) or `vitest`/`jest` (TS) test file in the same turn. Tests must execute (pass or fail with a clear assertion), not just exist.
3. **Pillar declaration.** Every new module/class in `v2/src/**` opens with a docstring header:
   ```
   Pillar: <Stable Core | Scenario Pack | Configuration Layer | Customization Layer>
   Phase: <1..7 from development_plan.md>
   ```
4. **Plug-and-play.** Backend must run headless (no frontend dependency). Frontend must accept `VITE_BACKEND_URL` and consume the generated OpenAPI client. No hidden coupling, no shared in-process state.
5. **Multi-agent ready.** All orchestrators implement the same async interface (`shared/orchestrator/base.py`). All emit events on the typed reasoning channel — never bury reasoning inside the answer string.
6. **Reasoning feed.** SSE channels: `reasoning`, `tool`, `answer`, `citation`, `error`. The frontend renders `reasoning` in a collapsible panel; o-series output flows there.
7. **No banned tech.** Do not introduce: Streamlit, Prompt Flow, Semantic Kernel, Poetry, direct `openai`/`AzureOpenAI` SDK calls in v2, Key Vault for app secrets. Use Foundry IQ + RBAC + Managed Identity.
8. **Every phase ends green.** `azd up` (or local `docker compose up`) must succeed at the end of each phase. Never leave a half-wired phase.
9. **Clean, modular, plug-and-play — anchored to dev_plan + pillars.** v1 is spaghetti and is being *replaced*, never imitated. Every addition (file, package, container, sidecar, abstraction, config format) must cite (a) a task # in [v2/docs/development_plan.md](../v2/docs/development_plan.md) §3.4 or §4, **and** (b) a pillar in [v2/docs/pillars_of_development.md](../v2/docs/pillars_of_development.md). v1 (`code/`, `docker/`, `infra/`) is a reference *only* for §2.1 removals; do not copy v1 patterns. CGSA/MACAE are read-only architectural references — adapt, never wholesale-copy. Defaults: one runtime per container, no invented sidecars, no premature abstractions, plug-and-play preserved (backend-only and frontend-only profiles must both boot).
10. **Ask before changing structure.** Any new top-level folder, new package in `pyproject.toml`/`package.json`, new module layout under `v2/src/**`, or rename across the tree requires explicit user confirmation **before** the planner emits a Work Order or the implementer touches a file. Structural decisions are not for agents to make unilaterally.

## Workflow contract

Use the dedicated agents for any non-trivial v2 work. They enforce the rules above:

- `cwyd-planner` — research + produce a one-unit work order (read-only).
- `cwyd-implementer` — write exactly one unit + test stub.
- `cwyd-tester` — fill the test, run it, report.

For trivial single-line edits, you may proceed directly — but still respect the test-first rule.

## Local development

- Python: `uv sync` from the repo root.
- v2 dev stack: `docker compose -f v2/docker/docker-compose.dev.yml up`.
- v2 backend-only: `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only up`.
- v2 frontend-only: `docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only up` (set `VITE_BACKEND_URL`).
- CI validation image: `docker build -f v2/docker/Dockerfile.ci-validate -t cwyd-ci .` then run.
