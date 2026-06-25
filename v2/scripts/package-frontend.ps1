# Pillar: Stable Core
# Phase:  1 (Frontend → App Service build-from-source)
#
# Thin PowerShell wrapper invoked by azd via the
# `services.frontend.hooks.prepackage.windows` block in v2/azure.yaml.
# Builds the Vite SPA, then stages the App Service deploy artifact
# (server + requirements.txt + static dist/) at
# v2/src/frontend/build-output/ via package_frontend.py. No backend URL
# is baked into the bundle -- the SPA reads it at runtime from the
# /config endpoint.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir '../src/frontend')
npm ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& uv run python (Join-Path $scriptDir 'package_frontend.py')
exit $LASTEXITCODE
