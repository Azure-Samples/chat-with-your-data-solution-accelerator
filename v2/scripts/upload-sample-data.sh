#!/usr/bin/env bash
# Pillar: Stable Core
# Phase:  7 (post-deploy sample-data seed)
#
# azd project-level `hooks.postdeploy` (posix) shim. Seeds curated sample
# documents and enqueues ingestion so chat grounds out-of-the-box. The
# Python uploader is idempotent, so re-running after a successful seed is
# a no-op.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run python "${SCRIPT_DIR}/upload_sample_data.py" "$@"
