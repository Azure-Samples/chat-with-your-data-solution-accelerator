#!/usr/bin/env bash
# Pillar: Stable Core
# Phase:  6 (Functions blueprints / modular RAG indexing pipeline)
#
# Thin POSIX wrapper around v2/scripts/prepackage_function.py invoked
# by azd via the `hooks.prepackage.posix` block in v2/azure.yaml. All
# logic lives in the Python script so behaviour is identical across
# platforms. Same wrapper pattern as post-provision.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run python "${SCRIPT_DIR}/prepackage_function.py" "$@"
