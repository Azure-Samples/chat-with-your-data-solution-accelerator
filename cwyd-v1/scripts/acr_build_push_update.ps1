<#
.SYNOPSIS
    Builds the application container images, pushes them to the per-deployment ACR,
    and updates the App Services / Function App.
.DESCRIPTION
    This script is a thin wrapper around the existing build_and_push_images.ps1 and
    update_app_service_images.ps1 scripts so it behaves like the combined workflow.
.PARAMETER ResourceGroupName
    The name of the Azure resource group containing the deployed resources.
.PARAMETER Mode
    Build mode: 'remote' (default) or 'local'.
.PARAMETER Tag
    Image tag to apply. Defaults to 'latest'.
.EXAMPLE
    .\scripts\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev"
.EXAMPLE
    .\scripts\acr_build_push_update.ps1 -ResourceGroupName "rg-cwyd-dev" -Mode local -Tag v1.0.0
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [ValidateSet("remote", "local")]
    [string]$Mode = "remote",

    [Parameter(Mandatory = $false)]
    [string]$Tag = "latest"
)

# -------------------------------------------------------
# Resolve repo root (script lives in scripts/)
# -------------------------------------------------------
$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { chcp 65001 > $null 2>$null } catch {}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# Auto-load environment values from .azure/<env>/.env when present
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$azureDir = Join-Path $RepoRoot '.azure'
if (Test-Path $azureDir) {
    $envFiles = Get-ChildItem -Path $azureDir -Recurse -Filter '.env' -File -ErrorAction SilentlyContinue
    foreach ($ef in $envFiles) {
        try {
            $lines = Get-Content $ef.FullName | Where-Object { $_ -and ($_ -match '=') }
            $kv = @{}
            foreach ($l in $lines) {
                if ($l -match '^\s*([A-Za-z0-9_]+)\s*=\s*"?(.*?)"?\s*$') { $kv[$matches[1]] = $matches[2] }
            }
            if ($kv.ContainsKey('ACR_NAME')) { $AcrName = $kv['ACR_NAME'] }
            if ($kv.ContainsKey('ACR_LOGIN_SERVER')) { $AcrLoginServer = $kv['ACR_LOGIN_SERVER'] }
            if ($kv.ContainsKey('SERVICE_WEB_RESOURCE_NAME')) { $ServiceWebName = $kv['SERVICE_WEB_RESOURCE_NAME'] }
            if ($kv.ContainsKey('SERVICE_ADMINWEB_RESOURCE_NAME')) { $ServiceAdminwebName = $kv['SERVICE_ADMINWEB_RESOURCE_NAME'] }
            if ($kv.ContainsKey('SERVICE_FUNCTION_RESOURCE_NAME')) { $ServiceFunctionName = $kv['SERVICE_FUNCTION_RESOURCE_NAME'] }
            if ($kv.ContainsKey('AZURE_RESOURCE_GROUP')) { $EnvResourceGroup = $kv['AZURE_RESOURCE_GROUP'] }
            if ($AcrName -or $ServiceWebName -or $ServiceAdminwebName -or $ServiceFunctionName) {
                Write-Host "Loaded env values from $($ef.FullName)"
                if ($AcrName) { Write-Host "  ACR_NAME=$AcrName" }
                if ($AcrLoginServer) { Write-Host "  ACR_LOGIN_SERVER=$AcrLoginServer" }
                if ($ServiceWebName) { Write-Host "  SERVICE_WEB_RESOURCE_NAME=$ServiceWebName" }
                if ($ServiceAdminwebName) { Write-Host "  SERVICE_ADMINWEB_RESOURCE_NAME=$ServiceAdminwebName" }
                if ($ServiceFunctionName) { Write-Host "  SERVICE_FUNCTION_RESOURCE_NAME=$ServiceFunctionName" }
                break
            }
        } catch {
            # ignore parse errors
        }
    }
}

$Images = @(
    [pscustomobject]@{ Name = 'rag-webapp'; Dockerfile = 'docker/Frontend.Dockerfile' },
    [pscustomobject]@{ Name = 'rag-adminwebapp'; Dockerfile = 'docker/Admin.Dockerfile' },
    [pscustomobject]@{ Name = 'rag-backend'; Dockerfile = 'docker/Backend.Dockerfile' }
)

Write-Host "=============================================="
Write-Host " Build, Push & Update Images"
Write-Host " Resource Group : $ResourceGroupName"
Write-Host " Mode           : $Mode"
Write-Host " Image Tag      : $Tag"
Write-Host " Repo Root      : $RepoRoot"
Write-Host "=============================================="

# ---------------------------------------------------------------------------
# Discover shared resources
# ---------------------------------------------------------------------------
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

# -------------------------------------------------------
# Helper: get deployment outputs from Bicep
# -------------------------------------------------------
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
}# -------------------------------------------------------
# Build and push
# -------------------------------------------------------
Write-Host ""

if ($Mode -eq "local") {
    Write-Host "--- LOCAL BUILD (Docker daemon) ---"

    # Verify Docker is available
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed or not in PATH.`nInstall Docker Desktop or use '-Mode remote' instead."
        exit 1
    }

    $dockerInfo = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker daemon is not running. Start Docker Desktop and retry."
        exit 1
    }

    Write-Host "Logging in to ACR '$AcrName'..."
    az acr login --name $AcrName
    if ($LASTEXITCODE -ne 0) { Write-Error "ACR login failed."; exit 1 }

    foreach ($img in $Images) {
        $FullTag     = "${AcrLoginServer}/$($img.Name):${Tag}"
        $Dockerfile  = Join-Path $RepoRoot $img.Dockerfile

        Write-Host ""
        Write-Host "[$($img.Name)] Building from $($img.Dockerfile) ..."
        docker build `
            --file  $Dockerfile `
            --tag   $FullTag `
            $RepoRoot
        if ($LASTEXITCODE -ne 0) { Write-Error "Build failed for $($img.Name)."; exit 1 }

        Write-Host "[$($img.Name)] Pushing $FullTag ..."
        docker push $FullTag
        if ($LASTEXITCODE -ne 0) { Write-Error "Push failed for $($img.Name)."; exit 1 }

        Write-Host "[$($img.Name)] OK Done"
    }
}
else {
    Write-Host "--- REMOTE BUILD (ACR Tasks - no local Docker required) ---"
    Write-Host "    Note: your Azure identity needs Contributor or AcrPush access on the ACR."
    Write-Host ""

    foreach ($img in $Images) {
        $FullTag    = "$($img.Name):${Tag}"
        $Dockerfile = Join-Path $RepoRoot $img.Dockerfile

        Write-Host "[$($img.Name)] Submitting remote build to ACR '$AcrName' ..."
        az acr build `
            --registry  $AcrName `
            --image     $FullTag `
            --file      $Dockerfile `
            $RepoRoot
        if ($LASTEXITCODE -ne 0) { Write-Error "Remote build failed for $($img.Name)."; exit 1 }

        Write-Host "[$($img.Name)] OK Done"
    }
}

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
Write-Host ""
Write-Host "=============================================="
Write-Host " Build & Push Complete"
Write-Host "=============================================="
Write-Host " Images pushed to ${AcrLoginServer}:"
foreach ($img in $Images) {
    Write-Host "   ${AcrLoginServer}/$($img.Name):${Tag}"
}

# ---------------------------------------------------------------------------
# Helper: update a web app
# ---------------------------------------------------------------------------
function Update-WebApp {
    param(
        [string]$AppName,
        [string]$ImageName
    )

    $FullImage = "${AcrLoginServer}/${ImageName}:${Tag}"
    Write-Host "  Updating App Service: $AppName"
    Write-Host "    Image: $FullImage"

    # 1. Set container image
    az webapp config container set `
        --name $AppName `
        --resource-group $ResourceGroupName `
        --container-image-name $FullImage `
        --output none

    # 2. Set DOCKER_REGISTRY_SERVER_URL app setting
    az webapp config appsettings set `
        --name $AppName `
        --resource-group $ResourceGroupName `
        --settings "DOCKER_REGISTRY_SERVER_URL=https://${AcrLoginServer}" `
        --output none

    # 3. Enable ACR pull with user-assigned managed identity
    $ResourceId = "/subscriptions/${SubscriptionId}/resourceGroups/${ResourceGroupName}/providers/Microsoft.Web/sites/${AppName}"
    az resource update `
        --ids $ResourceId `
        --set "properties.siteConfig.acrUseManagedIdentityCreds=true" `
        --set "properties.siteConfig.acrUserManagedIdentityID=$MiClientId" `
        --output none

    # 4. Restart to apply changes
    az webapp restart `
        --name $AppName `
        --resource-group $ResourceGroupName
}

# ---------------------------------------------------------------------------
# Helper: update a function app
# ---------------------------------------------------------------------------
function Update-FunctionApp {
    param(
        [string]$AppName,
        [string]$ImageName
    )

    $FullImage = "${AcrLoginServer}/${ImageName}:${Tag}"
    Write-Host "  Updating Function App: $AppName"
    Write-Host "    Image: $FullImage"

    # Set the container image via the dedicated command. This lets az build the
    # "DOCKER|<image>" linuxFxVersion internally, avoiding passing a literal '|'
    # on the command line (cmd.exe would otherwise interpret it as a pipe and
    # fail with "'<registry>.azurecr.io' is not recognized ...").
    az functionapp config container set `
        --name $AppName `
        --resource-group $ResourceGroupName `
        --image $FullImage `
        --registry-server "https://${AcrLoginServer}" `
        --output none

    # Enable managed identity based ACR pull (no pipe characters here)
    $ResourceId = "/subscriptions/${SubscriptionId}/resourceGroups/${ResourceGroupName}/providers/Microsoft.Web/sites/${AppName}"

    az resource update `
        --ids $ResourceId `
        --set "properties.siteConfig.acrUseManagedIdentityCreds=true" `
        --set "properties.siteConfig.acrUserManagedIdentityID=$MiClientId" `
        --output none

    # Restart to apply changes
    az functionapp restart `
        --name $AppName `
        --resource-group $ResourceGroupName
}

# ---------------------------------------------------------------------------
# Discover and update each service
# ---------------------------------------------------------------------------
$ServiceImageMap = @{
    "web-docker"      = "rag-webapp"
    "adminweb-docker" = "rag-adminwebapp"
}

# -- Web apps --
Write-Host "Updating web App Services..."
foreach ($ServiceTag in @("web-docker", "adminweb-docker")) {
    $AppName = $null
    switch ($ServiceTag) {
        "web-docker"      { $AppName = $ServiceWebName }
        "adminweb-docker" { $AppName = $ServiceAdminwebName }
    }

    if ([string]::IsNullOrWhiteSpace($AppName)) {
        $AppListJson = az webapp list --resource-group $ResourceGroupName --output json 2>$null
        if (-not [string]::IsNullOrWhiteSpace($AppListJson)) {
            $apps = $AppListJson | ConvertFrom-Json
            # Try tag first
            $AppName = ($apps | Where-Object { $_.tags -and $_.tags.'azd-service-name' -eq $ServiceTag } | Select-Object -First 1).name

            # Fallback: try name pattern - match by 'admin' in name for adminweb, exclude admin for web
            if ([string]::IsNullOrWhiteSpace($AppName)) {
                if ($ServiceTag -eq "web-docker") {
                    $AppName = ($apps | Where-Object { $_.name -notlike "*admin*" } | Select-Object -First 1).name
                } else {
                    $AppName = ($apps | Where-Object { $_.name -like "*admin*" } | Select-Object -First 1).name
                }
            }

            # Fallback: try deployment outputs from Bicep
            if ([string]::IsNullOrWhiteSpace($AppName)) {
                $outputName = if ($ServiceTag -eq "web-docker") { "SERVICE_WEB_RESOURCE_NAME" } else { "SERVICE_ADMINWEB_RESOURCE_NAME" }
                $AppName = Get-DeploymentOutput -OutputName $outputName -ResourceGroup $ResourceGroupName
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($AppName)) {
        Write-Host "  WARNING: No App Service for tag azd-service-name='$ServiceTag' found - skipping."
        continue
    }
    Update-WebApp -AppName $AppName -ImageName $ServiceImageMap[$ServiceTag]
}

# -- Function App --
Write-Host ""
Write-Host "Updating Function App..."
$FuncAppName = $ServiceFunctionName
if (-not [string]::IsNullOrWhiteSpace($FuncAppName)) {
    Write-Host "  Using environment-provided Function App name: $FuncAppName"
} else {
    $FuncListJson = az functionapp list --resource-group $ResourceGroupName --output json 2>$null
    if (-not [string]::IsNullOrWhiteSpace($FuncListJson)) {
        $funcs = $FuncListJson | ConvertFrom-Json

        # Try tag first
        $FuncAppName = ($funcs | Where-Object { $_.tags -and $_.tags.'azd-service-name' -eq 'function-docker' } | Select-Object -First 1).name

        # Fallback: use first available
        if ([string]::IsNullOrWhiteSpace($FuncAppName) -and $funcs.Count -gt 0) {
            $FuncAppName = $funcs[0].name
        }

        # Fallback: try deployment outputs from Bicep
        if ([string]::IsNullOrWhiteSpace($FuncAppName)) {
            $FuncAppName = Get-DeploymentOutput -OutputName "SERVICE_FUNCTION_RESOURCE_NAME" -ResourceGroup $ResourceGroupName
            if (-not [string]::IsNullOrWhiteSpace($FuncAppName)) {
                Write-Host "  Debug: Found '$FuncAppName' from deployment output 'SERVICE_FUNCTION_RESOURCE_NAME'"
            }
        }
    }
}

if ([string]::IsNullOrWhiteSpace($FuncAppName)) {
    Write-Host "  WARNING: No Function App found in resource group '$ResourceGroupName' - skipping."
} else {
    Update-FunctionApp -AppName $FuncAppName -ImageName "rag-backend"
}

Write-Host ""
Write-Host "=============================================="
Write-Host " ACR Build, Push & Update complete"
Write-Host "=============================================="
