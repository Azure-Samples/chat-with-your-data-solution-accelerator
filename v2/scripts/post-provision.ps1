# Pillar: Stable Core
# Phase:  1 (Infrastructure + Project Skeleton, task #19)
#
# Thin PowerShell wrapper around v2/scripts/post_provision.py invoked by
# azd via the `hooks.postprovision.windows` block in v2/azure.yaml. All
# logic lives in the Python script so behaviour is identical across
# platforms.
#
# azd guarantees:
#   * cwd == the azure.yaml project directory (== v2/, not the repo root)
#   * every Bicep output prefixed AZURE_* is exported as an env var
#   * AZURE_ENV_* values from the typed-prompt block are also exported

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& uv run python (Join-Path $scriptDir 'post_provision.py') @args
exit $LASTEXITCODE
