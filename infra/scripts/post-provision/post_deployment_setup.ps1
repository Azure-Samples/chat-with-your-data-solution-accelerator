#Requires -Version 5.1
<#
.SYNOPSIS
    Post-deployment setup script for v2.

.DESCRIPTION
    Discovers resources from the resource group, handles WAF/private networking
    (temporarily enables public access), sets env vars, delegates to post_provision.py,
    then restores the original network state.

.PARAMETER ResourceGroupName
    The name of the Azure resource group containing the deployed resources.

.EXAMPLE
    .\post_deployment_setup.ps1 -ResourceGroupName "my-rg"
#>

param(
    [Parameter(Position = 0)]
    [string]$ResourceGroupName
)

$ErrorActionPreference = "Stop"

if (-not $ResourceGroupName) {
    # Try to read from .azure/<env>/.env file
    # Script is at infra/scripts/post-provision/ — go up 4 levels from file to reach repo root
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
    $azureDir = Join-Path $repoRoot ".azure"
    if (Test-Path $azureDir) {
        $envFiles = Get-ChildItem -Path $azureDir -Recurse -Filter ".env" -File
        foreach ($envFile in $envFiles) {
            $match = Select-String -Path $envFile.FullName -Pattern '^AZURE_RESOURCE_GROUP="?([^"]+)"?$'
            if ($match) {
                $ResourceGroupName = $match.Matches[0].Groups[1].Value
                break
            }
        }
    }
    # Try AZURE_RESOURCE_GROUP env var
    if (-not $ResourceGroupName) {
        $ResourceGroupName = $env:AZURE_RESOURCE_GROUP
    }
    # Prompt as last resort
    if (-not $ResourceGroupName) {
        $ResourceGroupName = Read-Host "Enter the resource group name"
        if (-not $ResourceGroupName) {
            Write-Error "Resource group name is required."
            exit 1
        }
    }
}

Write-Host ""
Write-Host "=============================================="
Write-Host " Post-Deployment Setup (v2)"
Write-Host " Resource Group: $ResourceGroupName"
Write-Host "=============================================="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# -------------------------------------------------------
# Track resources that need public access restored
# -------------------------------------------------------
$RestorePgName = ""
$ServerName = ""

function Invoke-Cleanup {
    # Remove temporary firewall rule
    if ($ServerName) {
        Write-Host "[OK] Removing temporary firewall rule..."
        az postgres flexible-server firewall-rule delete `
            --resource-group $ResourceGroupName `
            --server-name $ServerName `
            --name "AllowPostDeploySetup" `
            --yes 2>$null | Out-Null
    }
    # Restore public access to Disabled on PostgreSQL
    if ($RestorePgName) {
        Write-Host "[OK] Disabling public access on PostgreSQL '$RestorePgName'..."
        $null = az postgres flexible-server update --resource-group $ResourceGroupName `
            --name $RestorePgName --public-access Disabled 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to disable public access on PostgreSQL. Please disable manually."
        }
    }
}

try {
    # -------------------------------------------------------
    # Discover resources and export env vars for post_provision.py
    # -------------------------------------------------------
    $env:AZURE_RESOURCE_GROUP = $ResourceGroupName

    # PostgreSQL
    $ServerFqdn = az postgres flexible-server list --resource-group $ResourceGroupName `
        --query "[0].fullyQualifiedDomainName" -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) { $ServerFqdn = "" }

    if ($ServerFqdn) {
        $ServerName = $ServerFqdn.Split('.')[0]
        $env:AZURE_POSTGRES_HOST = $ServerFqdn
        $env:AZURE_POSTGRES_NAME = $ServerName
        $env:AZURE_DB_TYPE = "postgresql"
        # Clear any stale CosmosDB-mode vars from previous runs
        $env:AZURE_AI_SEARCH_ENDPOINT = ""
        Write-Host "[OK] Discovered PostgreSQL: $ServerName ($ServerFqdn)"

        # --- WAF / Private Networking handling ---
        $PgPublicAccess = az postgres flexible-server show --resource-group $ResourceGroupName `
            --name $ServerName --query "network.publicNetworkAccess" -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { $PgPublicAccess = "" }

        if ($PgPublicAccess -eq "Disabled") {
            Write-Host "PostgreSQL has public access disabled (private networking detected)."
            Write-Host "[OK] Temporarily enabling public access on PostgreSQL '$ServerName'..."
            $PgErr = az postgres flexible-server update --resource-group $ResourceGroupName `
                --name $ServerName --public-access Enabled 2>&1
            if ($PgErr -match "(?i)error") {
                Write-Error "Failed to enable public access on PostgreSQL.`n  $PgErr"
                exit 1
            }
            $RestorePgName = $ServerName
            Write-Host "Waiting for PostgreSQL network change to propagate..."
            Start-Sleep -Seconds 30
        }

        # Wait for PostgreSQL server to be ready
        Write-Host "Waiting for PostgreSQL server to be ready..."
        $MaxRetries = 30
        $RetryInterval = 30
        for ($i = 1; $i -le $MaxRetries; $i++) {
            $PgState = az postgres flexible-server show --resource-group $ResourceGroupName `
                --name $ServerName --query "state" -o tsv 2>$null
            if ($PgState -eq "Ready") {
                Write-Host "PostgreSQL server is ready."
                break
            }
            Write-Host "  [$i/$MaxRetries] Server not ready (state: $PgState). Retrying in ${RetryInterval}s..."
            Start-Sleep -Seconds $RetryInterval
        }

        # Add temporary firewall rule for deployer's IP
        try {
            $PublicIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 10).Trim()
        } catch {
            $PublicIp = ""
        }
        if ($PublicIp) {
            Write-Host "[OK] Adding temporary firewall rule for IP $PublicIp..."
            az postgres flexible-server firewall-rule create `
                --resource-group $ResourceGroupName `
                --server-name $ServerName `
                --name "AllowPostDeploySetup" `
                --start-ip-address $PublicIp `
                --end-ip-address $PublicIp 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Firewall rule creation may have failed."
            }
        }
    } else {
        $env:AZURE_DB_TYPE = "cosmosdb"
        Write-Host "[OK] No PostgreSQL found; assuming CosmosDB mode."

        # AI Search (CosmosDB mode only — PostgreSQL uses pgvector for indexing)
        $SearchName = az search service list --resource-group $ResourceGroupName `
            --query "[0].name" -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { $SearchName = "" }
        if ($SearchName) {
            $env:AZURE_AI_SEARCH_ENDPOINT = "https://$SearchName.search.windows.net"
            Write-Host "[OK] Discovered AI Search: $SearchName"
        }
    }

    # OpenAI / AI Services (for knowledge base seed)
    $aiQuery = '[?kind==`AIServices` || kind==`OpenAI`] | [0].properties.endpoint'
    $AiServicesEndpoint = az cognitiveservices account list --resource-group $ResourceGroupName --query $aiQuery -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) { $AiServicesEndpoint = "" }
    if ($AiServicesEndpoint) {
        $env:AZURE_AI_SERVICES_ENDPOINT = $AiServicesEndpoint
        $env:AZURE_OPENAI_ENDPOINT = $AiServicesEndpoint
        Write-Host "[OK] Discovered AI Services: $AiServicesEndpoint"
    }

    # GPT deployment (first deployment that isn't an embedding model)
    $aiNameQuery = '[?kind==`AIServices` || kind==`OpenAI`] | [0].name'
    $AiAccountName = az cognitiveservices account list --resource-group $ResourceGroupName --query $aiNameQuery -o tsv 2>$null
    if ($AiAccountName) {
        $gptQuery = '[?contains(properties.model.name,`gpt`) || contains(properties.model.name,`o1`) || contains(properties.model.name,`o3`) || contains(properties.model.name,`o4-mini`)] | [0].name'
        $GptDeployment = az cognitiveservices account deployment list `
            --resource-group $ResourceGroupName `
            --name $AiAccountName `
            --query $gptQuery -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { $GptDeployment = "" }
        if ($GptDeployment) {
            $env:AZURE_OPENAI_GPT_DEPLOYMENT = $GptDeployment
            Write-Host "[OK] Discovered GPT deployment: $GptDeployment"
        }
    }

    # Fallback for BYO / cross-subscription Foundry: the OpenAI account and GPT
    # model live outside this resource group, so the in-RG lookups above find
    # nothing. Read the authoritative endpoint and deployment the backend
    # container app was deployed with.
    if (-not $AiServicesEndpoint -or -not $GptDeployment) {
        $BackendName = az containerapp list --resource-group $ResourceGroupName `
            --query "[?contains(name,'backend')] | [0].name" -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { $BackendName = "" }
        if ($BackendName) {
            if (-not $AiServicesEndpoint) {
                $AiServicesEndpoint = az containerapp show --resource-group $ResourceGroupName --name $BackendName `
                    --query "properties.template.containers[0].env[?name=='AZURE_OPENAI_ENDPOINT'].value | [0]" -o tsv 2>$null
                if ($LASTEXITCODE -ne 0) { $AiServicesEndpoint = "" }
                if ($AiServicesEndpoint) {
                    $env:AZURE_AI_SERVICES_ENDPOINT = $AiServicesEndpoint
                    $env:AZURE_OPENAI_ENDPOINT = $AiServicesEndpoint
                    Write-Host "[OK] Discovered AI Services from backend app '$BackendName': $AiServicesEndpoint"
                }
            }
            if (-not $GptDeployment) {
                $GptDeployment = az containerapp show --resource-group $ResourceGroupName --name $BackendName `
                    --query "properties.template.containers[0].env[?name=='AZURE_OPENAI_GPT_DEPLOYMENT'].value | [0]" -o tsv 2>$null
                if ($LASTEXITCODE -ne 0) { $GptDeployment = "" }
                if ($GptDeployment) {
                    $env:AZURE_OPENAI_GPT_DEPLOYMENT = $GptDeployment
                    Write-Host "[OK] Discovered GPT deployment from backend app '$BackendName': $GptDeployment"
                }
            }
        }
    }

    # Deployer UPN
    $DeployerUpn = az ad signed-in-user show --query "userPrincipalName" -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) { $DeployerUpn = "" }
    if ($DeployerUpn) {
        $env:AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME = $DeployerUpn
    }

    Write-Host ""
    Write-Host "--- Running post_provision.py ---"
    Write-Host ""

    # Run the Python script (uses uv if available, falls back to python)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv run python "$ScriptDir\post_provision.py"
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        python3 "$ScriptDir\post_provision.py"
    } else {
        python "$ScriptDir\post_provision.py"
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "post_provision.py failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "=============================================="
    Write-Host " Post-Deployment Setup Complete"
    Write-Host "=============================================="
} finally {
    Invoke-Cleanup
}
