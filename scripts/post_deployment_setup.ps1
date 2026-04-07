<#
.SYNOPSIS
    Post-deployment setup script for Chat With Your Data Solution Accelerator.
    Run this manually after 'azd provision' / 'azd up' completes.
.DESCRIPTION
    This single script performs two tasks:
      1. Sets the Function App client key (retrieved from Key Vault).
      2. Creates PostgreSQL tables (if a PostgreSQL server exists in the resource group).
    Only the resource group name is required — all other resource names are auto-discovered.
    If private networking (WAF) is enabled, the script temporarily enables public access
    on Key Vault and PostgreSQL, performs the operations, then restores the original state.
.PARAMETER ResourceGroupName
    The name of the Azure resource group containing the deployed resources.
.EXAMPLE
    ./scripts/post_deployment_setup.ps1 -ResourceGroupName "rg-cwyd-dev"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName
)

$ErrorActionPreference = "Stop"

Write-Host "=============================================="
Write-Host " Post-Deployment Setup"
Write-Host " Resource Group: $ResourceGroupName"
Write-Host "=============================================="
# Ensure rdbms-connect extension is installed (required for ad-admin commands)
az extension add --name rdbms-connect --yes 2>$null | Out-Null
# Track resources that need public access restored to Disabled
$resourcesToRestore = @()

# -------------------------------------------------------
# Helper: wait with retry
# -------------------------------------------------------
function Wait-ForCondition {
    param(
        [scriptblock]$Condition,
        [string]$Description,
        [int]$MaxRetries = 30,
        [int]$RetryIntervalSeconds = 20
    )
    for ($i = 1; $i -le $MaxRetries; $i++) {
        if (& $Condition) { return $true }
        Write-Host "  [$i/$MaxRetries] $Description — retrying in ${RetryIntervalSeconds}s..."
        Start-Sleep -Seconds $RetryIntervalSeconds
    }
    Write-Warning "⚠ $Description did not succeed after $($MaxRetries * $RetryIntervalSeconds) seconds."
    return $false
}

# -------------------------------------------------------
# Helper: restore public network access on tracked resources
# -------------------------------------------------------
function Restore-NetworkAccess {
    if ($script:resourcesToRestore.Count -eq 0) { return }
    Write-Host ""
    Write-Host "--- Restoring private networking ---"
    foreach ($res in $script:resourcesToRestore) {
        Write-Host "✓ Disabling public access on $($res.type) '$($res.name)'..."
        switch ($res.type) {
            "keyvault" {
                az keyvault update --name $res.name --resource-group $ResourceGroupName --public-network-access Disabled 2>$null | Out-Null
            }
            "postgres" {
                az postgres flexible-server update --resource-group $ResourceGroupName --name $res.name --public-access Disabled 2>$null | Out-Null
            }
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Public access disabled on '$($res.name)'."
        } else {
            Write-Warning "  ⚠ Failed to disable public access on '$($res.name)'. Please disable manually."
        }
    }
}

# -------------------------------------------------------
# STEP 1 — Set Function App Client Key
# -------------------------------------------------------
Write-Host ""
Write-Host "--- Step 1: Set Function App Client Key ---"

# Discover function app
$functionApps = az functionapp list --resource-group $ResourceGroupName --query "[].name" -o tsv 2>$null
if (-not $functionApps) {
    Write-Warning "⚠ No function apps found in resource group '$ResourceGroupName'. Skipping function key setup."
}
else {
    $functionAppName = ($functionApps -split "`n")[0].Trim()
    Write-Host "✓ Discovered function app: $functionAppName"

    # Discover key vault
    $keyVaults = az keyvault list --resource-group $ResourceGroupName --query "[].name" -o tsv 2>$null
    if (-not $keyVaults) {
        Write-Warning "⚠ No Key Vault found. Skipping function key setup."
    }
    else {
        $keyVaultName = ($keyVaults -split "`n")[0].Trim()
        Write-Host "✓ Discovered Key Vault: $keyVaultName"

        # Ensure the current user has 'Key Vault Secrets User' role on the Key Vault
        $currentUserOid = az ad signed-in-user show --query "id" -o tsv 2>$null
        if ($currentUserOid) {
            $kvResourceId = az keyvault show --name $keyVaultName --resource-group $ResourceGroupName --query "id" -o tsv 2>$null
            if ($kvResourceId) {
                $kvSecretsUserRoleId = "4633458b-17de-408a-b874-0445c86b69e6"
                $existingAssignment = az role assignment list --assignee $currentUserOid --role $kvSecretsUserRoleId --scope $kvResourceId --query "[0].id" -o tsv 2>$null
                if (-not $existingAssignment) {
                    Write-Host "✓ Assigning 'Key Vault Secrets User' role to current user on Key Vault..."
                    $roleOutput = az role assignment create --assignee-object-id $currentUserOid --assignee-principal-type User --role $kvSecretsUserRoleId --scope $kvResourceId 2>&1 | Out-String
                    if ($LASTEXITCODE -ne 0) {
                        Write-Warning "⚠ Failed to assign Key Vault Secrets User role."
                        Write-Warning "  $roleOutput"
                    } else {
                        Write-Host "✓ Role assigned. Waiting 30s for propagation..."
                        Start-Sleep -Seconds 30
                    }
                } else {
                    Write-Host "✓ Current user already has 'Key Vault Secrets User' role on Key Vault."
                }
            }
        } else {
            Write-Warning "⚠ Could not determine current user OID. Skipping Key Vault role assignment."
        }

        # Check if Key Vault public access is disabled (WAF/private networking)
        $kvPublicAccess = az keyvault show --name $keyVaultName --resource-group $ResourceGroupName --query "properties.publicNetworkAccess" -o tsv 2>$null
        if ($kvPublicAccess -eq "Disabled") {
            Write-Host "Key Vault has public access disabled (private networking detected)."
            Write-Host "✓ Temporarily enabling public access on Key Vault '$keyVaultName'..."
            $kvOutput = az keyvault update --name $keyVaultName --resource-group $ResourceGroupName --public-network-access Enabled 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) {
                Write-Error "✗ Failed to enable public access on Key Vault. Cannot proceed.`n  $kvOutput"
                exit 1
            }
            $resourcesToRestore += @{ type = "keyvault"; name = $keyVaultName }
            Write-Host "Waiting for Key Vault network change to propagate..."
            Start-Sleep -Seconds 30
        }

        # Retrieve function key from Key Vault
        Write-Host "✓ Retrieving function key from Key Vault..."
        $functionKey = az keyvault secret show --vault-name $keyVaultName --name "FUNCTION-KEY" --query "value" -o tsv
        if ($LASTEXITCODE -ne 0 -or -not $functionKey) {
            Restore-NetworkAccess
            Write-Error "✗ Failed to retrieve 'FUNCTION-KEY' secret from Key Vault '$keyVaultName'."
            exit 1
        }

        # Wait for function app to be running
        Write-Host "Waiting for function app to be ready..."
        $ready = Wait-ForCondition -Description "Function app '$functionAppName' not running yet" -Condition {
            $state = az functionapp show --name $functionAppName --resource-group $ResourceGroupName --query "state" -o tsv 2>$null
            return ($LASTEXITCODE -eq 0 -and $state -eq "Running")
        }

        # Set the function key via REST API (with retries — host runtime may not be ready immediately)
        Write-Host "✓ Setting function key 'ClientKey' on '$functionAppName'..."
        $subscriptionId = az account show --query "id" -o tsv
        $uri = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.Web/sites/$functionAppName/host/default/functionKeys/clientKey?api-version=2023-01-01"
        $bodyObj = @{ properties = @{ name = "ClientKey"; value = $functionKey } }
        $bodyJson = $bodyObj | ConvertTo-Json -Compress
        $tempBodyFile = [System.IO.Path]::GetTempFileName()
        try {
            Set-Content -Path $tempBodyFile -Value $bodyJson -Encoding utf8
            $keySet = Wait-ForCondition -Description "Function host runtime not ready yet" -MaxRetries 10 -RetryIntervalSeconds 30 -Condition {
                az rest --method put --uri $uri --body "@$tempBodyFile" 2>$null | Out-Null
                return ($LASTEXITCODE -eq 0)
            }
            if (-not $keySet) {
                Restore-NetworkAccess
                Write-Error "✗ Failed to set function key on '$functionAppName' after retries."
                exit 1
            }
        } finally {
            Remove-Item -Path $tempBodyFile -Force -ErrorAction SilentlyContinue
        }
        Write-Host "✓ Function key set successfully."
    }
}

# -------------------------------------------------------
# STEP 2 — Create PostgreSQL Tables (if applicable)
# -------------------------------------------------------
Write-Host ""
Write-Host "--- Step 2: Create PostgreSQL Tables ---"

$pgServers = az postgres flexible-server list --resource-group $ResourceGroupName --query "[].fullyQualifiedDomainName" -o tsv 2>$null
if (-not $pgServers) {
    Write-Host "No PostgreSQL Flexible Server found in resource group. Skipping table creation."
}
else {
    $serverFqdn = ($pgServers -split "`n")[0].Trim()
    $serverName = $serverFqdn.Split('.')[0]
    Write-Host "✓ Discovered PostgreSQL server: $serverName ($serverFqdn)"

    # Check if PostgreSQL public access is disabled (WAF/private networking)
    $pgPublicAccess = az postgres flexible-server show --resource-group $ResourceGroupName --name $serverName --query "network.publicNetworkAccess" -o tsv 2>$null
    if ($pgPublicAccess -eq "Disabled") {
        Write-Host "PostgreSQL has public access disabled (private networking detected)."
        Write-Host "✓ Temporarily enabling public access on PostgreSQL '$serverName'..."
        $pgOutput = az postgres flexible-server update --resource-group $ResourceGroupName --name $serverName --public-access Enabled 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Restore-NetworkAccess
            Write-Error "✗ Failed to enable public access on PostgreSQL. Cannot proceed.`n  $pgOutput"
            exit 1
        }
        $resourcesToRestore += @{ type = "postgres"; name = $serverName }
        Write-Host "Waiting for PostgreSQL network change to propagate..."
        Start-Sleep -Seconds 30
    }

    # Wait for PostgreSQL to be ready
    Write-Host "Waiting for PostgreSQL server to be ready..."
    Wait-ForCondition -Description "PostgreSQL server '$serverName' not ready" -Condition {
        $state = az postgres flexible-server show --resource-group $ResourceGroupName --name $serverName --query "state" -o tsv 2>$null
        return ($LASTEXITCODE -eq 0 -and $state -eq "Ready")
    } | Out-Null

    # Add firewall rule for current machine
    $publicIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -UseBasicParsing).Trim()
    Write-Host "✓ Adding temporary firewall rule for IP $publicIp..."
    az postgres flexible-server firewall-rule create `
        --resource-group $ResourceGroupName `
        --name $serverName `
        --rule-name "AllowPostDeploySetup" `
        --start-ip-address $publicIp `
        --end-ip-address $publicIp 2>$null | Out-Null

    # Get current user info for local Entra auth to PostgreSQL
    $currentUserUpn = az ad signed-in-user show --query "userPrincipalName" -o tsv 2>$null
    $currentUserOid = az ad signed-in-user show --query "id" -o tsv 2>$null
    if (-not $currentUserUpn -or -not $currentUserOid) {
        Restore-NetworkAccess
        Write-Error "✗ Could not determine current signed-in user. Ensure you are logged in with 'az login'."
        exit 1
    }
    Write-Host "✓ Current user: $currentUserUpn ($currentUserOid)"

    # Ensure current user is a PostgreSQL Entra administrator
    $existingAdmins = az postgres flexible-server ad-admin list --resource-group $ResourceGroupName --server-name $serverName --query "[].objectId" -o tsv 2>$null
    $isAdmin = $false
    if ($existingAdmins) {
        foreach ($adminOid in ($existingAdmins -split "`n")) {
            if ($adminOid.Trim() -eq $currentUserOid) { $isAdmin = $true; break }
        }
    }
    $addedPgAdmin = $false
    if (-not $isAdmin) {
        Write-Host "✓ Adding current user as PostgreSQL Entra administrator..."
        $adminOutput = az postgres flexible-server ad-admin create `
            --resource-group $ResourceGroupName `
            --server-name $serverName `
            --display-name $currentUserUpn `
            --object-id $currentUserOid `
            --type User 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "⚠ Failed to add current user as PostgreSQL admin. Table creation may fail."
            Write-Warning "  $adminOutput"
        } else {
            $addedPgAdmin = $true
            Write-Host "✓ PostgreSQL admin added. Waiting 60s for propagation..."
            Start-Sleep -Seconds 60
        }
    } else {
        Write-Host "✓ Current user is already a PostgreSQL Entra administrator."
    }

    try {
        # Install Python dependencies
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        $requirementsFile = Join-Path $scriptDir "data_scripts" "requirements.txt"
        if (Test-Path $requirementsFile) {
            Write-Host "✓ Installing Python dependencies..."
            pip install --user -r $requirementsFile 2>&1 | Out-Null
        }

        Write-Host "✓ Creating tables..."
        $pythonScript = Join-Path $scriptDir "data_scripts" "setup_postgres_tables.py"
        python $pythonScript $serverFqdn $currentUserUpn

        if ($LASTEXITCODE -ne 0) {
            Write-Error "✗ Failed to create PostgreSQL tables."
        }
    }
    finally {
        # Remove temporary PostgreSQL admin if we added it
        if ($addedPgAdmin) {
            Write-Host "✓ Removing temporary PostgreSQL Entra admin for current user..."
            az postgres flexible-server ad-admin delete `
                --resource-group $ResourceGroupName `
                --server-name $serverName `
                --object-id $currentUserOid `
                --yes 2>$null
        }
        # Clean up firewall rule
        Write-Host "✓ Removing temporary firewall rule..."
        az postgres flexible-server firewall-rule delete `
            --resource-group $ResourceGroupName `
            --name $serverName `
            --rule-name "AllowPostDeploySetup" `
            --yes 2>$null
    }

    Write-Host "✓ PostgreSQL table creation completed."
}

# -------------------------------------------------------
# STEP 3 — Restore private networking (if it was enabled)
# -------------------------------------------------------
Restore-NetworkAccess

Write-Host ""
Write-Host "=============================================="
Write-Host " Post-Deployment Setup Complete"
Write-Host "=============================================="
