#Requires -Version 5.1
<#
.SYNOPSIS
    Backend authentication setup (v2) -- one-shot, closes the anonymous-admin
    exposure end to end.

.DESCRIPTION
    The backend Container App ships with EXTERNAL ingress and no ingress-level
    authentication, so any anonymous caller can reach /api/admin/* directly
    (the frontend's Easy Auth never covers backend traffic -- they are separate
    Container Apps). This script:

      1. Creates (or reuses) a single Entra app registration shared by both
         Container Apps.
      2. Ensures Easy Auth is enabled on the FRONTEND Container App (configures
         it with the shared app registration when it is not already set up).
      3. Enables Easy Auth on the BACKEND Container App with the unauthenticated
         action set to return 401, and configures it to accept the frontend's
         token audience -- so the browser's /.auth/me token is accepted with no
         cross-app consent, delegated scope, or redeploy.
      4. Turns on the backend's in-app admin-auth gate and verifies that an
         anonymous admin call is rejected.

    This is a MANUAL, re-runnable step. Run it AFTER 'azd up' and 'az login'.

.PARAMETER ResourceGroupName
    The name of the Azure resource group containing the deployed resources.

.EXAMPLE
    .\setup_auth.ps1 -ResourceGroupName "my-rg"

.NOTES
    Requires an Azure CLI session (az login) whose account can configure the
    Container Apps AND create / read an Entra app registration (Application
    Developer or Application Administrator directory role).
#>

param(
    [Parameter(Position = 0)]
    [string]$ResourceGroupName
)

$ErrorActionPreference = "Stop"

# -------------------------------------------------------
# Resolve the resource group (arg -> .azure/<env>/.env -> env -> prompt)
# -------------------------------------------------------
if (-not $ResourceGroupName) {
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
    if (-not $ResourceGroupName) {
        $ResourceGroupName = $env:AZURE_RESOURCE_GROUP
    }
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
Write-Host " Backend Authentication Setup (v2)"
Write-Host " Resource Group: $ResourceGroupName"
Write-Host "=============================================="

# -------------------------------------------------------
# Confirm an authenticated Azure CLI session
# -------------------------------------------------------
$tenantId = az account show --query "tenantId" -o tsv 2>$null
if (-not $tenantId) {
    Write-Error "Not logged in to Azure CLI. Run 'az login' first."
    exit 1
}
Write-Host "[OK] Azure CLI session tenant: $tenantId"
$issuer = "https://login.microsoftonline.com/$tenantId/v2.0"

# -------------------------------------------------------
# Discover the backend and frontend Container Apps
# -------------------------------------------------------
$backendName = az containerapp list --resource-group $ResourceGroupName `
    --query "[?contains(name,'backend')] | [0].name" -o tsv 2>$null
if (-not $backendName) {
    Write-Error "No backend Container App found in '$ResourceGroupName'. Deploy the stack (azd up) first."
    exit 1
}
$backendFqdn = az containerapp show --resource-group $ResourceGroupName --name $backendName `
    --query "properties.configuration.ingress.fqdn" -o tsv 2>$null
Write-Host "[OK] Backend Container App: $backendName ($backendFqdn)"

$frontendName = az containerapp list --resource-group $ResourceGroupName `
    --query "[?contains(name,'frontend')] | [0].name" -o tsv 2>$null
$frontendFqdn = ""
if ($frontendName) {
    $frontendFqdn = az containerapp show --resource-group $ResourceGroupName --name $frontendName `
        --query "properties.configuration.ingress.fqdn" -o tsv 2>$null
    Write-Host "[OK] Frontend Container App: $frontendName ($frontendFqdn)"
}
else {
    Write-Host "[WARN] No frontend Container App found; only the backend will be configured."
}

# -------------------------------------------------------
# Create or reuse the shared Entra app registration. Idempotent: reuse an
# existing registration with the same display name. Register BOTH the backend
# and frontend Easy Auth callbacks so the one app can front both Container Apps.
# -------------------------------------------------------
$appDisplayName = "$backendName-auth"
Write-Host ""
Write-Host "--- Entra app registration: $appDisplayName ---"

$appId = az ad app list --display-name $appDisplayName --query "[0].appId" -o tsv 2>$null

if (-not $appId) {
    Write-Host "[OK] Creating app registration '$appDisplayName'..."
    $appId = az ad app create --display-name $appDisplayName `
        --sign-in-audience AzureADMyOrg --query "appId" -o tsv 2>$null
    if (-not $appId) {
        Write-Error @"
Could not create the app registration. Your account likely lacks directory
permissions (needs the 'Application Developer' or 'Application Administrator'
role). Ask a directory admin to create an app registration named
'$appDisplayName', then re-run this script.
"@
        exit 1
    }
}
else {
    Write-Host "[OK] Reusing existing app registration (appId $appId)."
}

# Set the identifier URI so api://<appId> is a valid audience. Idempotent.
az ad app update --id $appId --identifier-uris "api://$appId" 2>$null | Out-Null

# Register both Easy Auth callbacks on the shared app (idempotent).
$redirectUris = @()
if ($backendFqdn) { $redirectUris += "https://$backendFqdn/.auth/login/aad/callback" }
if ($frontendFqdn) { $redirectUris += "https://$frontendFqdn/.auth/login/aad/callback" }
if ($redirectUris.Count -gt 0) {
    az ad app update --id $appId --web-redirect-uris $redirectUris 2>$null | Out-Null
}

# Easy Auth's login flow requests an id_token via the implicit/hybrid grant,
# so the app registration must enable ID-token issuance (otherwise login fails
# with AADSTS700054 'response_type id_token is not enabled'). Idempotent.
az ad app update --id $appId --enable-id-token-issuance true 2>$null | Out-Null

# -------------------------------------------------------
# Register the frontend SPA redirect URI on the shared app. The browser-
# side MSAL flow (PKCE public client, no secret) redirects back to the
# SPA origin. SPA redirect URIs live under the Graph `spa` property, which
# the az CLI does not surface, so patch them via `az rest`. The body is
# written to a temp file and the app is addressed by object id -- on
# Windows the az cmd wrapper mangles an inline JSON `--body` (braces/quotes
# corrupt the argument list) and the alternate-key `(appId='...')` URL.
# Idempotent.
# -------------------------------------------------------
if ($frontendFqdn) {
    $spaRedirect = "https://$frontendFqdn"
    $appObjectId = az ad app show --id $appId --query "id" -o tsv 2>$null
    if (-not $appObjectId) {
        Write-Host "[WARN] Could not resolve the app object id; skipping SPA redirect URI."
    }
    else {
        $graphUri = "https://graph.microsoft.com/v1.0/applications/$appObjectId"
        $spaBodyFile = New-TemporaryFile
        (@{ spa = @{ redirectUris = @($spaRedirect) } } | ConvertTo-Json -Compress) |
            Set-Content -Path $spaBodyFile -Encoding utf8 -NoNewline
        $spaOut = az rest --method PATCH --uri $graphUri `
            --headers "Content-Type=application/json" `
            --body "@$spaBodyFile" 2>&1
        $spaExit = $LASTEXITCODE
        Remove-Item $spaBodyFile -Force -ErrorAction SilentlyContinue
        if ($spaExit -ne 0) {
            Write-Host "[WARN] Could not register the SPA redirect URI ($spaRedirect):`n$spaOut"
        }
        else {
            Write-Host "[OK] Registered SPA redirect URI: $spaRedirect"
        }
    }
}

# -------------------------------------------------------
# The frontend SPA owns sign-in via MSAL, so it must load anonymously -- a
# RedirectToLoginPage Easy Auth gate would block the JS from ever running.
# Disable ingress Easy Auth on the frontend and wire the MSAL parameters
# (client id + tenant) as env vars the SPA reads from /config at runtime.
# The all-zero/empty cases degrade to the anonymous default user locally.
# -------------------------------------------------------
if ($frontendName) {
    az containerapp auth update `
        --resource-group $ResourceGroupName --name $frontendName `
        --enabled false 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Could not disable Easy Auth on the frontend."
    }
    az containerapp update `
        --resource-group $ResourceGroupName --name $frontendName `
        --set-env-vars "AZURE_AUTH_CLIENT_ID=$appId" "AZURE_TENANT_ID=$tenantId" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Could not set the frontend MSAL env vars."
    }
    Write-Host "[OK] Frontend set for MSAL (Easy Auth disabled; AZURE_AUTH_CLIENT_ID / AZURE_TENANT_ID set)."
}

# -------------------------------------------------------
# Enable Easy Auth on the backend ingress, fail closed. The browser
# forwards the MSAL id_token, whose audience is the shared app's client
# id; the backend validates that audience (bearer validation only, no
# client secret stored). `/api/health` is excluded so the liveness probe
# stays publicly reachable (no token required).
# -------------------------------------------------------
Write-Host ""
Write-Host "--- Enabling Easy Auth on $backendName (fail closed) ---"

# The MSAL id_token audience is the shared app client id ($appId).
$tokenAud = $appId

$providerOut = az containerapp auth microsoft update `
    --resource-group $ResourceGroupName --name $backendName `
    --client-id $appId `
    --issuer $issuer `
    --allowed-audiences $tokenAud `
    --yes 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to configure the Microsoft identity provider on the backend:`n$providerOut"
    exit 1
}

az containerapp auth update `
    --resource-group $ResourceGroupName --name $backendName `
    --enabled true `
    --unauthenticated-client-action Return401 `
    --excluded-paths "/api/health" `
    --redirect-provider azureActiveDirectory 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to enable Easy Auth on the backend ingress."
    exit 1
}
Write-Host "[OK] Easy Auth enabled; unauthenticated requests now return 401 at the ingress."

# -------------------------------------------------------
# Configure backend ingress CORS so the SPA's cross-origin calls succeed.
# ACA Easy Auth returns 401 on the unauthenticated CORS preflight (the
# browser sends OPTIONS with no token), which blocks the request before
# the app's own CORS middleware can run. The ingress CORS policy answers
# the preflight at the envoy layer -- ahead of Easy Auth -- so the ingress
# must own CORS here. The backend container sets no BACKEND_CORS_ORIGINS,
# so the app emits no Access-Control-Allow-Origin and there is no duplicate
# header. Not a credentialed request (the SPA uses plain fetch), so the
# bearer flows via the allowed `authorization` header without cookies.
# -------------------------------------------------------
if ($frontendFqdn) {
    az containerapp ingress cors enable `
        --resource-group $ResourceGroupName --name $backendName `
        --allowed-origins "https://$frontendFqdn" `
        --allowed-methods GET POST PUT DELETE PATCH OPTIONS `
        --allowed-headers "*" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Could not configure backend ingress CORS for https://$frontendFqdn."
    }
    else {
        Write-Host "[OK] Backend ingress CORS allows https://$frontendFqdn."
    }
}

# -------------------------------------------------------
# Turn on the app-layer defense-in-depth gate (code default is already true).
# -------------------------------------------------------
az containerapp update --resource-group $ResourceGroupName --name $backendName `
    --set-env-vars "AZURE_REQUIRE_ADMIN_AUTH=true" 2>$null | Out-Null
Write-Host "[OK] Backend app-layer admin-auth gate set (AZURE_REQUIRE_ADMIN_AUTH=true)."

# -------------------------------------------------------
# Record values in the azd environment (reference + CORS origin).
# -------------------------------------------------------
$audience = "api://$appId"
if (Get-Command azd -ErrorAction SilentlyContinue) {
    azd env set AZURE_BACKEND_AUTH_CLIENT_ID $appId 2>$null | Out-Null
    azd env set AZURE_BACKEND_AUTH_AUDIENCE $audience 2>$null | Out-Null
    if ($frontendFqdn) {
        azd env set BACKEND_CORS_ORIGINS "https://$frontendFqdn" 2>$null | Out-Null
    }
    Write-Host "[OK] Recorded AZURE_BACKEND_AUTH_CLIENT_ID / AUDIENCE (and CORS origin) in the azd env."
}
else {
    Write-Host "[WARN] azd not on PATH; set these manually in .azure/<env>/.env:"
    Write-Host "    AZURE_BACKEND_AUTH_CLIENT_ID=$appId"
    Write-Host "    AZURE_BACKEND_AUTH_AUDIENCE=$audience"
    if ($frontendFqdn) { Write-Host "    BACKEND_CORS_ORIGINS=https://$frontendFqdn" }
}

# -------------------------------------------------------
# Verify the ingress now rejects anonymous admin calls (auth changes take a
# few minutes to propagate, so retry with backoff).
# -------------------------------------------------------
$verifyUrl = "https://$backendFqdn/api/admin/status"
if ($backendFqdn) {
    Write-Host ""
    Write-Host "--- Verifying anonymous admin call is rejected (allow time to propagate) ---"
    $verified = $false
    foreach ($i in 1..6) {
        try {
            $resp = Invoke-WebRequest -Uri $verifyUrl -Method GET -SkipHttpErrorCheck -UseBasicParsing
            $code = [int]$resp.StatusCode
        }
        catch {
            $code = 0
        }
        if ($code -eq 401 -or $code -eq 403) {
            Write-Host "[OK] Anonymous call returned HTTP $code -- backend is secured."
            $verified = $true
            break
        }
        Write-Host "  [$i/6] Got HTTP $code; retrying in 20s..."
        Start-Sleep -Seconds 20
    }
    if (-not $verified) {
        Write-Host "[WARN] Not yet returning 401/403. Easy Auth may need more time; re-check manually."
    }
}

Write-Host ""
Write-Host "=============================================="
Write-Host " Backend Authentication Setup Complete"
Write-Host "=============================================="
Write-Host ""
Write-Host "The frontend and backend are now protected by Easy Auth. Signed-in users"
Write-Host "reach the app; the browser forwards its login token to the backend, which"
Write-Host "accepts it; anonymous callers get 401 at the backend ingress."
Write-Host ""
Write-Host "If you had other sessions open, sign out and back in so the browser picks"
Write-Host "up a fresh token. Re-verify any time with:"
Write-Host "    curl -i $verifyUrl"
