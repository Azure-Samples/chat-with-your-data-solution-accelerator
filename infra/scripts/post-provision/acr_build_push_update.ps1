<#
.SYNOPSIS
    Builds the v2 application container images, pushes them to the per-deployment ACR,
    and updates the Container Apps (frontend, backend, function). The function
    service runs as a Container App, so all three are updated the same way.
.DESCRIPTION
    Uses ACR Tasks (remote build - no local Docker required) to build three images
    from docker/Dockerfile.frontend, docker/Dockerfile.backend, docker/Dockerfile.functions,
    then updates the deployed services discovered by their azd-service-name tags.
.PARAMETER ResourceGroupName
    The name of the Azure resource group containing the deployed resources.
.PARAMETER Tag
    Image tag to apply. Defaults to 'latest'.
.EXAMPLE
    .\infra\scripts\post-provision\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev"
.EXAMPLE
    .\infra\scripts\post-provision\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev" -Tag v1.0.0
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Console encoding (UTF-8 for clean output from az / python)
# =============================================================================
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { chcp 65001 > $null 2>$null } catch {}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# =============================================================================
# Constants
# =============================================================================

# v2 image map: matches docker/ Dockerfiles at repo root and bicep-defined image names.
# (Bicep hard-codes rag-functions for the function app; frontend/backend are updated by this script.)
$Images = @(
    [pscustomobject]@{ Name = 'rag-frontend';  Dockerfile = 'docker/Dockerfile.frontend' },
    [pscustomobject]@{ Name = 'rag-backend';   Dockerfile = 'docker/Dockerfile.backend' },
    [pscustomobject]@{ Name = 'rag-functions'; Dockerfile = 'docker/Dockerfile.functions' }
)

# Service discovery map for the update phase: azd-service-name -> image name.
$ContainerAppServiceMap = @(
    [pscustomobject]@{ ServiceTag = 'frontend'; ImageName = 'rag-frontend' },
    [pscustomobject]@{ ServiceTag = 'backend';  ImageName = 'rag-backend' },
    [pscustomobject]@{ ServiceTag = 'function'; ImageName = 'rag-functions' }
)

# Tracks whether this script temporarily opened a locked-down (WAF) ACR so the
# finally block knows whether it needs to re-lock it.
$script:AcrOpenedForBuild = $false

# =============================================================================
# Helper functions
# =============================================================================

# Get a Bicep deployment output value from the most recent RG deployment.
# Fallback discovery helper; returns $null when unavailable.
function Get-DeploymentOutput {
    param(
        [string]$OutputName,
        [string]$ResourceGroup
    )

    try {
        $deploymentName = az deployment group list `
            --resource-group $ResourceGroup `
            --query "[0].name" `
            --output tsv 2>$null

        if ([string]::IsNullOrWhiteSpace($deploymentName)) {
            return $null
        }

        $output = az deployment group show `
            --name $deploymentName `
            --resource-group $ResourceGroup `
            --query "properties.outputs.$OutputName.value" `
            --output tsv 2>$null

        return $output
    } catch {
        return $null
    }
}

# ---- ACR public access (WAF auto-detect; try/finally pattern from CGSA) ------

# Temporarily enable public network access on the ACR when it is locked down
# (WAF mode) so the remote build can reach the registry.
function Enable-AcrPublicAccess {
    $publicAccess = az acr show -n $AcrName --query publicNetworkAccess --output tsv 2>$null
    if ($publicAccess -eq 'Disabled') {
        Write-Host "===== ACR public access is disabled (WAF mode) - temporarily enabling for build =====" -ForegroundColor Yellow
        az acr update -n $AcrName --public-network-enabled true --default-action Allow --output none --only-show-errors
        if ($LASTEXITCODE -ne 0) { Write-Error "Failed to enable ACR public access."; exit 1 }
        $script:AcrOpenedForBuild = $true
        Write-Host "Waiting 45s for network rule propagation..." -ForegroundColor Yellow
        Start-Sleep -Seconds 45
    }
}

# Re-lock the ACR if (and only if) this script opened it.
function Restore-AcrPublicAccess {
    if ($script:AcrOpenedForBuild) {
        Write-Host "===== Re-locking ACR (disabling public network access) =====" -ForegroundColor Yellow
        az acr update -n $AcrName --public-network-enabled false --default-action Deny --output none --only-show-errors
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to re-disable ACR public access. Re-lock manually: az acr update -n $AcrName --public-network-enabled false --default-action Deny"
        }
    }
}

# ---- Service updates ---------------------------------------------------------
# Update a Container App (v2 frontend + backend) to a new image. Bicep already
# wires the ACR registry with the UAMI, so only the image is set here.
function Update-ContainerApp {
    param(
        [string]$AppName,
        [string]$ImageName
    )

    $FullImage = "${AcrLoginServer}/${ImageName}:${Tag}"
    $RevisionSuffix = Get-Date -Format "yyyyMMddHHmmss"
    Write-Host "  Updating Container App: $AppName"
    Write-Host "    Image: $FullImage"
    Write-Host "    Revision suffix: $RevisionSuffix"

    az containerapp update `
        --name $AppName `
        --resource-group $ResourceGroupName `
        --image $FullImage `
        --revision-suffix $RevisionSuffix `
        --output none
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to update Container App '$AppName'."; exit 1 }
}

# =============================================================================
# 1. Resolve repo root (Resource group is authoritative for all discovery)
# =============================================================================
# Script lives at <repo>/infra/scripts/post-provision/, so walk up 3 levels for the repo root.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir))

Write-Host "=============================================="
Write-Host " Build, Push & Update Images"
Write-Host " Resource Group : $ResourceGroupName"
Write-Host " Image Tag      : $Tag"
Write-Host " Repo Root      : $RepoRoot"
Write-Host "=============================================="

# =============================================================================
# 2. Discover shared resources (ACR, managed identity, subscription)
# =============================================================================
Write-Host "Discovering resources in resource group '$ResourceGroupName'..."

if (-not $AcrName) {
    $AcrName = az acr list `
        --resource-group $ResourceGroupName `
        --query "[0].name" `
        --output tsv 2>$null
}

if ([string]::IsNullOrWhiteSpace($AcrName)) {
    Write-Error "No Azure Container Registry found in resource group '$ResourceGroupName'.`nRun 'azd provision' to create infrastructure first."
    exit 1
}

if (-not $AcrLoginServer) {
    $AcrLoginServer = "$AcrName.azurecr.io"
}

$MiClientId = az identity list `
    --resource-group $ResourceGroupName `
    --query "[0].clientId" `
    --output tsv 2>$null

if ([string]::IsNullOrWhiteSpace($MiClientId)) {
    Write-Error "No user-assigned managed identity found in resource group '$ResourceGroupName'."
    exit 1
}

$SubscriptionId = az account show --query id --output tsv

Write-Host "  ACR             : $AcrLoginServer"
Write-Host "  Managed identity: $MiClientId"
Write-Host ""

# =============================================================================
# 3. Build and push images (remote ACR Tasks build)
# =============================================================================
Write-Host ""
Write-Host "--- REMOTE BUILD (ACR Tasks - no local Docker required) ---"
Write-Host "    Note: your Azure identity needs Contributor or AcrPush access on the ACR."
Write-Host ""

try {
    Enable-AcrPublicAccess

    foreach ($img in $Images) {
        $FullTag    = "$($img.Name):${Tag}"
        $ContextDir = Join-Path $env:TEMP "acr-build-context-$($img.Name)"

        Remove-Item $ContextDir -Recurse -Force -ErrorAction SilentlyContinue
        $null = New-Item -ItemType Directory -Path $ContextDir
        Copy-Item -Path (Join-Path $RepoRoot 'src')            -Destination $ContextDir -Recurse
        Copy-Item -Path (Join-Path $RepoRoot 'docker')         -Destination $ContextDir -Recurse
        Copy-Item -Path (Join-Path $RepoRoot 'pyproject.toml') -Destination $ContextDir
        Copy-Item -Path (Join-Path $RepoRoot 'uv.lock')        -Destination $ContextDir

        Write-Host "[$($img.Name)] Submitting remote build to ACR '$AcrName' ..."
        az acr build `
            --registry  $AcrName `
            --image     $FullTag `
            --file      $img.Dockerfile `
            $ContextDir
        if ($LASTEXITCODE -ne 0) {
            Remove-Item $ContextDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Error "Remote build failed for $($img.Name)."
            exit 1
        }

        Remove-Item $ContextDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[$($img.Name)] OK Done"
    }
} finally {
    Restore-AcrPublicAccess
}

# =============================================================================
# 4. Build & push summary
# =============================================================================
Write-Host ""
Write-Host "=============================================="
Write-Host " Build & Push Complete"
Write-Host "=============================================="
Write-Host " Images pushed to ${AcrLoginServer}:"
foreach ($img in $Images) {
    Write-Host "   ${AcrLoginServer}/$($img.Name):${Tag}"
}

# =============================================================================
# 5. Discover and update Container Apps (frontend + backend + function)
# =============================================================================
Write-Host ""
Write-Host "Updating Container Apps..."

$ContainerAppListJson = az containerapp list --resource-group $ResourceGroupName --output json 2>$null
$containerApps = @()
if (-not [string]::IsNullOrWhiteSpace($ContainerAppListJson)) {
    $containerApps = $ContainerAppListJson | ConvertFrom-Json
}

foreach ($entry in $ContainerAppServiceMap) {
    $AppName = ($containerApps `
        | Where-Object { $_.tags -and $_.tags.'azd-service-name' -eq $entry.ServiceTag } `
        | Select-Object -First 1).name

    # Fallback: name pattern (Bicep uses ca-<service>-<suffix>)
    if ([string]::IsNullOrWhiteSpace($AppName)) {
        $AppName = ($containerApps `
            | Where-Object { $_.name -like "ca-$($entry.ServiceTag)-*" } `
            | Select-Object -First 1).name
    }

    if ([string]::IsNullOrWhiteSpace($AppName)) {
        Write-Host "  WARNING: No Container App for azd-service-name='$($entry.ServiceTag)' in RG '$ResourceGroupName' - skipping."
        continue
    }

    Update-ContainerApp -AppName $AppName -ImageName $entry.ImageName
}

Write-Host ""
Write-Host "=============================================="
Write-Host " ACR Build, Push & Update complete"
Write-Host "=============================================="
