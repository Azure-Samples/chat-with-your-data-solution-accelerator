# Pillar: Stable Core
# Phase:  6 (Functions blueprints / modular RAG indexing pipeline)
#
# Thin PowerShell wrapper around v2/scripts/prepackage_function.py
# invoked by azd via the `hooks.prepackage.windows` block in
# v2/azure.yaml. All logic lives in the Python script so behaviour is
# identical across platforms. Same wrapper pattern as post-provision.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& uv run python (Join-Path $scriptDir 'prepackage_function.py') @args
exit $LASTEXITCODE
