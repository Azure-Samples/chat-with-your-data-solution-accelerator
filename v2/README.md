# CWYD v2

This is the **active development tree** for the Chat With Your Data
(CWYD) solution accelerator. Post root-reorg, the v2 code tree now lives
at the **repo root** (`src/`, `infra/`, `docker/`, `scripts/`, `tests/`,
`azure.yaml`); only the v2 documentation and this README remain under
`v2/`. The repo-root [README](../README.md) is still being modernized to
describe v2 — until that lands it reflects v1.

v2 replaces the v1 Flask/Streamlit/Semantic-Kernel/Prompt-Flow stack
with FastAPI + LangGraph + Microsoft Agent Framework + Foundry IQ, on a
plug-and-play registry primitive that supports first-party and
third-party provider extensions side-by-side.

## Where to start

| What you need              | Where to look                                                              |
| -------------------------- | -------------------------------------------------------------------------- |
| Roadmap, phases, scope     | [docs/development_plan.md](docs/development_plan.md)                       |
| Architecture pillars       | [docs/pillars_of_development.md](docs/pillars_of_development.md)           |
| Extend with a plugin       | [docs/extending.md](docs/extending.md)                                     |
| Environment variables      | [docs/env-vars.md](docs/env-vars.md)                                       |
| Infrastructure (Bicep/azd) | [docs/infrastructure.md](docs/infrastructure.md)                           |
| Architecture decision log  | [docs/adr/](docs/adr/)                                                     |
| Repo-wide rules            | [../.github/copilot-instructions.md](../.github/copilot-instructions.md)   |

## Local development

```bash
# From the repo root
uv sync

# Full v2 stack (backend + frontend + dependencies)
docker compose -f docker/docker-compose.dev.yml up

# Backend-only profile (headless)
docker compose -f docker/docker-compose.dev.yml --profile backend-only up

# Frontend-only profile (set VITE_BACKEND_URL to point at a running backend)
docker compose -f docker/docker-compose.dev.yml --profile frontend-only up
```

## Testing

Run the default suite (unit tests + shared discipline gates) from the repo
root. The `smoke` and `integration` markers are deselected by default,
so this lane is fully hermetic — it never touches the network:

```bash
uv run pytest -q
```

### Integration lane (live Azure)

An opt-in lane boots the **real** FastAPI app in-process and drives it
against the **real** Azure data-plane services configured in `.env`
(LLM, Foundry IQ / Azure Search, chat-history database). It asserts on
behavioral invariants — grounded answers, citation presence, the fixed
out-of-domain fallback, the SSE channel set, the admin role gate, and a
chat-history CRUD round-trip — never on environment-specific values.

Prerequisites: a populated `.env` (see [docs/env-vars.md](docs/env-vars.md))
and `az login`. The lane self-skips when `.env` is absent or missing the
required keys, so it is safe to leave deselected in CI.

```bash
az login
uv run --env-file .env pytest -m integration tests/integration -v
```

The `--env-file .env` flag injects the real configuration; the lane re-loads
it past the unit-suite's env stripper. Tests that need a specific backend
(e.g. cosmosdb mode, the `agent_framework` orchestrator) skip with a
capability reason when the configured deployment does not match.

## Layout

```
Repo root (v2 code tree)
├── docker/         # docker-compose + Dockerfiles for dev + CI validation
├── infra/          # Bicep + azd templates
├── scripts/        # helper scripts (env parsing, smoke checks)
├── src/
│   ├── backend/    # FastAPI app, providers, orchestrators, routers
│   ├── frontend/   # React + Vite SPA
│   └── functions/  # Azure Functions blueprints (RAG indexing pipeline)
└── tests/          # pytest tree (unit + integration + shared gates)

v2/
└── docs/           # plans, ADRs, env vars, extension guide
```
