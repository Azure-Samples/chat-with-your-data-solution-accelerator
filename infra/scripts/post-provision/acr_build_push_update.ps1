<#
.SYNOPSIS
    Builds the v2 container images, pushes them to ACR, and rolls out new
    revisions to all three Container Apps (frontend, backend, function).
.DESCRIPTION
    Uses ACR Tasks (remote build — no local Docker required) to build images
    from docker/Dockerfile.*, then updates the deployed Container Apps.
    Works for both plain and WAF (private networking) deployments: the ACR
    is temporarily unlocked for the remote build and re-locked on exit.
.PARAMETER ResourceGroupName
    Azure resource group that contains the ACR and Container Apps.
.PARAMETER Tag
    Image tag to push. Defaults to 'latest'.
.EXAMPLE
    .\infra\scripts\post-provision\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev"
.EXAMPLE
    .\infra\scripts\post-provision\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev" -Tag v1.2.0
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"
$ScriptStart = [datetime]::UtcNow

# --- UTF-8 output (clean az / python output) ---------------------------------
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { chcp 65001 > $null 2>&1 } catch {}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8       = '1'

# =============================================================================
# Service definitions — one entry per deployable service.
# Add a row here to onboard a new service; nothing else needs to change.
# =============================================================================
$Services = @(
    [pscustomobject]@{ Name = 'rag-frontend';  Dockerfile = 'docker/Dockerfile.frontend';  ServiceTag = 'frontend' },
    [pscustomobject]@{ Name = 'rag-backend';   Dockerfile = 'docker/Dockerfile.backend';   ServiceTag = 'backend'  },
    [pscustomobject]@{ Name = 'rag-functions'; Dockerfile = 'docker/Dockerfile.functions'; ServiceTag = 'function' }
)

# Tracks whether THIS run temporarily opened a WAF-locked ACR (for cleanup)
$script:AcrOpenedForBuild = $false

# =============================================================================
# Helpers — print utilities
# =============================================================================

function Write-Step {
    param([int]$Number, [int]$Total, [string]$Title)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  Step $Number / $Total  |  $Title" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Write-Success { param([string]$Msg)  Write-Host "  [OK]  $Msg" -ForegroundColor Green  }
function Write-Info    { param([string]$Msg)  Write-Host "  >>   $Msg" -ForegroundColor White  }
function Write-Warn    { param([string]$Msg)  Write-Host "  [!]  $Msg" -ForegroundColor Yellow }
function Write-Elapsed {
    $elapsed = [datetime]::UtcNow - $ScriptStart
    Write-Host ("  Elapsed: {0:mm\:ss}" -f $elapsed) -ForegroundColor DarkGray
}

# =============================================================================
# Helpers — ACR public-access management (WAF deployments)
# =============================================================================

function Enable-AcrPublicAccess {
    $publicAccess = az acr show -n $AcrName --query publicNetworkAccess --output tsv 2>$null
    if ($publicAccess -eq 'Disabled') {
        Write-Warn "ACR is WAF-locked — temporarily enabling public network access for build"
        az acr update -n $AcrName --public-network-enabled true --default-action Allow `
            --output none --only-show-errors
        if ($LASTEXITCODE -ne 0) { Write-Error "Could not enable ACR public access."; exit 1 }
        $script:AcrOpenedForBuild = $true
        Write-Warn "Waiting 45 s for network rule propagation..."
        Start-Sleep -Seconds 45
    } else {
        Write-Info "ACR public access: $publicAccess (no WAF unlock needed)"
    }
}

function Restore-AcrPublicAccess {
    if ($script:AcrOpenedForBuild) {
        Write-Warn "Re-locking ACR (disabling public network access)"
        az acr update -n $AcrName --public-network-enabled false --default-action Deny `
            --output none --only-show-errors
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Failed to re-lock. Run manually: az acr update -n $AcrName --public-network-enabled false --default-action Deny"
        } else {
            Write-Success "ACR re-locked"
        }
    }
}

# =============================================================================
# Helper — roll out a new revision to a Container App
# =============================================================================

function Update-ContainerApp {
    param([string]$AppName, [string]$ImageName)

    $fullImage = "${AcrLoginServer}/${ImageName}:${Tag}"
    $revSuffix = Get-Date -Format "yyyyMMddHHmmss"

    Write-Info "Deploying  : $AppName"
    Write-Info "  Image    : $fullImage"
    Write-Info "  Suffix   : $revSuffix"

    az containerapp update `
        --name            $AppName `
        --resource-group  $ResourceGroupName `
        --image           $fullImage `
        --revision-suffix $revSuffix `
        --output none
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to update Container App '$AppName'."; exit 1 }
    Write-Success "$AppName updated"
}

# =============================================================================
# Banner
# =============================================================================

$totalSteps = 4
$svcList    = ($Services | ForEach-Object { $_.Name }) -join ', '
Write-Host ""
Write-Host "  CWYD v2  |  Build - Push - Deploy" -ForegroundColor Cyan
Write-Host "  Resource Group : $ResourceGroupName" -ForegroundColor Cyan
Write-Host "  Image Tag      : $Tag" -ForegroundColor Cyan
Write-Host "  Services       : $svcList" -ForegroundColor Cyan

# =============================================================================
# Step 1 - Discover resources
# =============================================================================
Write-Step 1 $totalSteps "Discover ACR and Container Apps"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir))
Write-Info "Repo root : $RepoRoot"

if (-not $AcrName) {
    $AcrName = az acr list --resource-group $ResourceGroupName --query "[0].name" --output tsv 2>$null
}
if ([string]::IsNullOrWhiteSpace($AcrName)) {
    Write-Error "No ACR found in '$ResourceGroupName'. Run 'azd provision' first."
    exit 1
}
if (-not $AcrLoginServer) { $AcrLoginServer = "$AcrName.azurecr.io" }
Write-Success "ACR : $AcrLoginServer"

$MiClientId = az identity list --resource-group $ResourceGroupName --query "[0].clientId" --output tsv 2>$null
if ([string]::IsNullOrWhiteSpace($MiClientId)) {
    Write-Warn "No UAMI found — image pulls may fail if Bicep UAMI wiring is missing"
} else {
    Write-Success "UAMI client id : $MiClientId"
}
Write-Elapsed

# =============================================================================
# Step 2 - Remote ACR build (one image at a time)
# =============================================================================
Write-Step 2 $totalSteps "Remote Build via ACR Tasks (no local Docker needed)"
Write-Info "Your Azure identity needs 'AcrPush' or 'Contributor' on the ACR."

$buildCount  = 0
$totalBuilds = $Services.Count

try {
    Enable-AcrPublicAccess

    foreach ($svc in $Services) {
        $buildCount++
        Write-Host ""
        Write-Host "  [$buildCount/$totalBuilds] $($svc.Name)" -ForegroundColor White
        Write-Info "  Dockerfile : $($svc.Dockerfile)"
        Write-Info "  Target tag : $AcrLoginServer/$($svc.Name):$Tag"

        # Minimal build context: only files each Dockerfile actually needs
        $contextDir = Join-Path $env:TEMP "acr-ctx-$($svc.Name)"
        Remove-Item $contextDir -Recurse -Force -ErrorAction SilentlyContinue
        $null = New-Item -ItemType Directory -Path $contextDir

        Write-Info "  Copying build context..."
        Copy-Item -Path (Join-Path $RepoRoot 'src')            -Destination $contextDir -Recurse
        Copy-Item -Path (Join-Path $RepoRoot 'docker')         -Destination $contextDir -Recurse
        Copy-Item -Path (Join-Path $RepoRoot 'pyproject.toml') -Destination $contextDir
        Copy-Item -Path (Join-Path $RepoRoot 'uv.lock')        -Destination $contextDir

        Write-Info "  Submitting to ACR Tasks — streaming build log..."
        az acr build `
            --registry $AcrName `
            --image    "$($svc.Name):$Tag" `
            --file     $svc.Dockerfile `
            $contextDir
        $buildExit = $LASTEXITCODE
        Remove-Item $contextDir -Recurse -Force -ErrorAction SilentlyContinue

        if ($buildExit -ne 0) {
            Write-Error "Build failed for $($svc.Name). See ACR Task log above."
            exit 1
        }
        Write-Success "$($svc.Name):$Tag pushed"
    }
} finally {
    Restore-AcrPublicAccess
}
Write-Elapsed

# =============================================================================
# Step 3 - Deploy new revisions to Container Apps
# =============================================================================
Write-Step 3 $totalSteps "Deploy New Revisions to Container Apps"

$containerApps = @()
$caJson = az containerapp list --resource-group $ResourceGroupName --output json 2>$null
if (-not [string]::IsNullOrWhiteSpace($caJson)) {
    $containerApps = $caJson | ConvertFrom-Json
}
Write-Info "Found $($containerApps.Count) Container App(s) in '$ResourceGroupName'"

foreach ($svc in $Services) {
    Write-Host ""
    # Primary: azd-service-name tag set by azd provision
    $appName = ($containerApps |
        Where-Object { $_.tags -and $_.tags.'azd-service-name' -eq $svc.ServiceTag } |
        Select-Object -First 1).name

    # Fallback: Bicep naming convention  ca-<service>-<suffix>
    if ([string]::IsNullOrWhiteSpace($appName)) {
        $appName = ($containerApps |
            Where-Object { $_.name -like "ca-$($svc.ServiceTag)-*" } |
            Select-Object -First 1).name
    }

    if ([string]::IsNullOrWhiteSpace($appName)) {
        Write-Warn "No Container App found for service tag '$($svc.ServiceTag)' — skipping"
        continue
    }
    Update-ContainerApp -AppName $appName -ImageName $svc.Name
}
Write-Elapsed

# =============================================================================
# Step 4 - Summary
# =============================================================================
Write-Step 4 $totalSteps "Done"

$elapsed = [datetime]::UtcNow - $ScriptStart
Write-Host ""
Write-Host "  Images deployed to $AcrLoginServer :" -ForegroundColor Green
foreach ($svc in $Services) {
    Write-Host "    $AcrLoginServer/$($svc.Name):$Tag" -ForegroundColor Green
}
Write-Host ""
Write-Success ("Completed in {0:mm\:ss}" -f $elapsed)

