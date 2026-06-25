#!/usr/bin/env bash
# Pillar: Stable Core
# Phase:  1 (Frontend → App Service build-from-source)
#
# Thin POSIX wrapper invoked by azd via the
# `services.frontend.hooks.prepackage.posix` block in v2/azure.yaml.
# Builds the Vite SPA, then stages the App Service deploy artifact
# (server + requirements.txt + static dist/) at
# v2/src/frontend/build-output/ via package_frontend.py. No backend URL
# is baked into the bundle -- the SPA reads it at runtime from the
# /config endpoint.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../src/frontend"
npm ci
npm run build
exec uv run python "${SCRIPT_DIR}/package_frontend.py"
