# Pillar: Stable Core
# Phase:  7 (post-deploy sample-data seed)
#
# azd project-level `hooks.postdeploy` (windows) shim. Seeds curated
# sample documents and enqueues ingestion so chat grounds out-of-the-box.
# The Python uploader is idempotent, so re-running after a successful seed
# is a no-op.
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& uv run python (Join-Path $scriptDir 'upload_sample_data.py') @args
exit $LASTEXITCODE
