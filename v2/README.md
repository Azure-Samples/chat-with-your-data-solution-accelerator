# CWYD v2

This directory holds the **active development tree** for the Chat With
Your Data (CWYD) solution accelerator. The repo-root [README](../README.md)
still describes v1 (`code/` + `infra/` + `tests/`); v2 lives here.

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
docker compose -f v2/docker/docker-compose.dev.yml up

# Backend-only profile (headless)
docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only up

# Frontend-only profile (set VITE_BACKEND_URL to point at a running backend)
docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only up
```

## Testing

Run the default suite (unit tests + shared discipline gates) from the `v2/`
directory. The `smoke` and `integration` markers are deselected by default,
so this lane is fully hermetic — it never touches the network:

```bash
cd v2
uv run pytest -q
```

### Integration lane (live Azure)

An opt-in lane boots the **real** FastAPI app in-process and drives it
against the **real** Azure data-plane services configured in `v2/.env`
(LLM, Foundry IQ / Azure Search, chat-history database). It asserts on
behavioral invariants — grounded answers, citation presence, the fixed
out-of-domain fallback, the SSE channel set, the admin role gate, and a
chat-history CRUD round-trip — never on environment-specific values.

Prerequisites: a populated `v2/.env` (see [docs/env-vars.md](docs/env-vars.md))
and `az login`. The lane self-skips when `v2/.env` is absent or missing the
required keys, so it is safe to leave deselected in CI.

```bash
cd v2
az login
uv run --env-file .env pytest -m integration tests/integration -v
```

The `--env-file .env` flag injects the real configuration; the lane re-loads
it past the unit-suite's env stripper. Tests that need a specific backend
(e.g. cosmosdb mode, the `agent_framework` orchestrator) skip with a
capability reason when the configured deployment does not match.

## Layout

```
v2/
├── docker/         # docker-compose + Dockerfiles for dev + CI validation
├── docs/           # plans, ADRs, env vars, extension guide
├── infra/          # Bicep + azd templates (v2-specific)
├── scripts/        # helper scripts (env parsing, smoke checks)
├── src/
│   ├── backend/    # FastAPI app, providers, orchestrators, routers
│   └── functions/  # Azure Functions blueprints (RAG indexing pipeline)
└── tests/          # pytest tree (unit + integration + shared gates)
```
