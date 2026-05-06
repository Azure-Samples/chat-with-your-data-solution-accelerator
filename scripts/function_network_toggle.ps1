param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("enable", "disable")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

# This hook only applies to container hosting; code hosting remains unchanged.
$hostingModel = $env:AZURE_APP_SERVICE_HOSTING_MODEL
if ($hostingModel -ne "container") {
    Write-Host "Skipping Function App network toggle: hosting model is '$hostingModel' (not container)."
    exit 0
}

$functionAppName = $env:SERVICE_FUNCTION_RESOURCE_NAME
$resourceGroup = $env:AZURE_RESOURCE_GROUP

if (-not $functionAppName -or -not $resourceGroup) {
    Write-Host "Skipping Function App network toggle: missing SERVICE_FUNCTION_RESOURCE_NAME or AZURE_RESOURCE_GROUP."
    exit 0
}

az functionapp show --name $functionAppName --resource-group $resourceGroup 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Skipping Function App network toggle: Function App '$functionAppName' not found in '$resourceGroup'."
    exit 0
}

# Only toggle when private endpoint exists, which is the WAF/private-networking scenario for container hosting.
$functionAppId = az functionapp show `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --query "id" `
    -o tsv 2>$null

$privateEndpointCount = az network private-endpoint list `
    --resource-group $resourceGroup `
    --query "length([?contains(privateLinkServiceConnections[].privateLinkServiceId, '$functionAppId')])" `
    -o tsv 2>$null

if ($LASTEXITCODE -ne 0 -or -not $privateEndpointCount -or [int]$privateEndpointCount -eq 0) {
    Write-Host "Skipping Function App network toggle: no private endpoint is configured on '$functionAppName'."
    exit 0
}

$currentPublicAccess = az functionapp show `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --query "publicNetworkAccess" `
    -o tsv

if ($Action -eq "enable") {
    if ($currentPublicAccess -eq "Enabled") {
        Write-Host "Function App public access already enabled; no change needed."
        exit 0
    }

    Write-Host "Temporarily enabling Function App public access for deployment."
    az functionapp update `
        --name $functionAppName `
        --resource-group $resourceGroup `
        --set publicNetworkAccess=Enabled | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to enable Function App public access."
    }

    Write-Host "Function App public access enabled."
    exit 0
}

if ($currentPublicAccess -eq "Disabled") {
    Write-Host "Function App public access already disabled; no change needed."
    exit 0
}

Write-Host "Restoring Function App to private-only access."
az functionapp update `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --set publicNetworkAccess=Disabled | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Failed to disable Function App public access."
}

Write-Host "Function App public access disabled."
