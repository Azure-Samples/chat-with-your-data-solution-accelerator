#!/bin/bash
set -e

# v2 uses uv (not Poetry) for Python dependency management.
uv sync

# Install pre-commit hooks. pre-commit is standalone dev tooling (not a project
# dependency), so install it as a uv-managed tool; the git hook it writes then
# resolves to a persistent interpreter at commit time.
uv tool install pre-commit
uv tool run pre-commit install

# Install frontend dependencies (v2 frontend lives under src/frontend).
(cd ./src/frontend && npm install)
