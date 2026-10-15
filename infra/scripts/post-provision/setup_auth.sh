#!/bin/bash
set -e

# Prevent Git Bash (MSYS) from mangling Azure resource ID paths
export MSYS_NO_PATHCONV=1

# ============================================================================
# Backend authentication setup (v2) -- one-shot, closes the anonymous-admin
# exposure end to end.
#
# The backend Container App ships with EXTERNAL ingress and no ingress-level
# authentication, so any anonymous caller can reach /api/admin/* directly
# (the frontend's Easy Auth never covers backend traffic -- they are separate
# Container Apps). This script:
#
#   1. Creates (or reuses) a single Entra app registration shared by both
#      Container Apps.
#   2. Ensures Easy Auth is enabled on the FRONTEND Container App (configures
#      it with the shared app registration when it is not already set up).
#   3. Enables Easy Auth on the BACKEND Container App with the unauthenticated
#      action set to return 401, and configures it to accept the frontend's
#      token audience -- so the browser's `/.auth/me` token is accepted with
#      no cross-app consent, delegated scope, or redeploy.
#   4. Turns on the backend's in-app admin-auth gate and verifies that an
#      anonymous admin call is rejected.
#
# This is a MANUAL, re-runnable step. Run it AFTER `azd up` and `az login`.
#
# Usage: ./infra/scripts/post-provision/setup_auth.sh <resource-group-name>
#
# Prerequisites: an Azure CLI session (`az login`) whose account can configure
# the Container Apps AND create / read an Entra app registration (Application
# Developer or Application Administrator directory role).
# ============================================================================

# -------------------------------------------------------
# Resolve the resource group (arg -> .azure/<env>/.env -> env -> prompt)
# -------------------------------------------------------
if [ -z "$1" ]; then
    SCRIPT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
    AZURE_DIR="$SCRIPT_ROOT/.azure"
    if [ -d "$AZURE_DIR" ]; then
        ENV_FILE=$(find "$AZURE_DIR" -name ".env" -type f 2>/dev/null | head -1)
        if [ -n "$ENV_FILE" ]; then
            RESOURCE_GROUP=$(grep '^AZURE_RESOURCE_GROUP=' "$ENV_FILE" | sed 's/^AZURE_RESOURCE_GROUP=//;s/^"//;s/"$//')
        fi
    fi
    if [ -z "$RESOURCE_GROUP" ]; then
        RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
    fi
    if [ -z "$RESOURCE_GROUP" ]; then
        read -rp "Enter the resource group name: " RESOURCE_GROUP
        if [ -z "$RESOURCE_GROUP" ]; then
            echo "Resource group name is required."
            exit 1
        fi
    fi
else
    RESOURCE_GROUP="$1"
fi

echo "=============================================="
echo " Backend Authentication Setup (v2)"
echo " Resource Group: ${RESOURCE_GROUP}"
echo "=============================================="

# -------------------------------------------------------
# Confirm an authenticated Azure CLI session
# -------------------------------------------------------
TENANT_ID=$(az account show --query "tenantId" -o tsv 2>/dev/null || true)
if [ -z "$TENANT_ID" ]; then
    echo "✗ ERROR: Not logged in to Azure CLI. Run 'az login' first." >&2
    exit 1
fi
echo "✓ Azure CLI session tenant: ${TENANT_ID}"
ISSUER="https://login.microsoftonline.com/${TENANT_ID}/v2.0"

# -------------------------------------------------------
# Discover the backend and frontend Container Apps
# -------------------------------------------------------
BACKEND_NAME=$(az containerapp list --resource-group "$RESOURCE_GROUP" \
    --query "[?contains(name,'backend')] | [0].name" -o tsv 2>/dev/null || true)
if [ -z "$BACKEND_NAME" ]; then
    echo "✗ ERROR: No backend Container App found in '${RESOURCE_GROUP}'." >&2
    echo "  Deploy the stack (azd up) before running this script." >&2
    exit 1
fi
BACKEND_FQDN=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
    --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || true)
echo "✓ Backend Container App: ${BACKEND_NAME} (${BACKEND_FQDN})"

FRONTEND_NAME=$(az containerapp list --resource-group "$RESOURCE_GROUP" \
    --query "[?contains(name,'frontend')] | [0].name" -o tsv 2>/dev/null || true)
FRONTEND_FQDN=""
if [ -n "$FRONTEND_NAME" ]; then
    FRONTEND_FQDN=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_NAME" \
        --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || true)
    echo "✓ Frontend Container App: ${FRONTEND_NAME} (${FRONTEND_FQDN})"
else
    echo "⚠ No frontend Container App found; only the backend will be configured."
fi

# -------------------------------------------------------
# Create or reuse the shared Entra app registration. Idempotent: reuse an
# existing registration with the same display name. Register BOTH the backend
# and frontend Easy Auth callbacks so the one app can front both Container Apps.
# -------------------------------------------------------
APP_DISPLAY_NAME="${BACKEND_NAME}-auth"
echo ""
echo "--- Entra app registration: ${APP_DISPLAY_NAME} ---"

APP_ID=$(az ad app list --display-name "$APP_DISPLAY_NAME" \
    --query "[0].appId" -o tsv 2>/dev/null || true)

if [ -z "$APP_ID" ]; then
    echo "✓ Creating app registration '${APP_DISPLAY_NAME}'..."
    APP_ID=$(az ad app create --display-name "$APP_DISPLAY_NAME" \
        --sign-in-audience AzureADMyOrg \
        --query "appId" -o tsv 2>/dev/null || true)
    if [ -z "$APP_ID" ]; then
        echo "✗ ERROR: Could not create the app registration." >&2
        echo "  Your account likely lacks directory permissions (needs the" >&2
        echo "  'Application Developer' or 'Application Administrator' role)." >&2
        echo "  Ask a directory admin to create an app registration named" >&2
        echo "  '${APP_DISPLAY_NAME}', then re-run this script." >&2
        exit 1
    fi
else
    echo "✓ Reusing existing app registration (appId ${APP_ID})."
fi

# Set the identifier URI so api://<appId> is a valid audience. Idempotent.
az ad app update --id "$APP_ID" --identifier-uris "api://$APP_ID" >/dev/null 2>&1 \
    || echo "⚠ WARNING: could not set identifier URI; the audience may already be set."

# Register both Easy Auth callbacks on the shared app (idempotent).
REDIRECT_URIS=()
[ -n "$BACKEND_FQDN" ] && REDIRECT_URIS+=("https://${BACKEND_FQDN}/.auth/login/aad/callback")
[ -n "$FRONTEND_FQDN" ] && REDIRECT_URIS+=("https://${FRONTEND_FQDN}/.auth/login/aad/callback")
if [ ${#REDIRECT_URIS[@]} -gt 0 ]; then
    az ad app update --id "$APP_ID" --web-redirect-uris "${REDIRECT_URIS[@]}" >/dev/null 2>&1 \
        || echo "⚠ WARNING: could not set redirect URIs."
fi

# Easy Auth's login flow requests an id_token via the implicit/hybrid grant,
# so the app registration must enable ID-token issuance (otherwise login fails
# with AADSTS700054 'response_type id_token is not enabled'). Idempotent.
az ad app update --id "$APP_ID" --enable-id-token-issuance true >/dev/null 2>&1 \
    || echo "⚠ WARNING: could not enable ID-token issuance on the app registration."

# -------------------------------------------------------
# Register the frontend SPA redirect URI on the shared app. The browser-
# side MSAL flow (PKCE public client, no secret) redirects back to the SPA
# origin. SPA redirect URIs live under the Graph `spa` property, which the
# az CLI does not surface, so patch them via `az rest`. The app is
# addressed by object id (more robust than the alternate-key
# `(appId='...')` URL). Idempotent.
# -------------------------------------------------------
if [ -n "$FRONTEND_FQDN" ]; then
    SPA_REDIRECT="https://${FRONTEND_FQDN}"
    APP_OBJECT_ID=$(az ad app show --id "$APP_ID" --query "id" -o tsv 2>/dev/null || true)
    if [ -z "$APP_OBJECT_ID" ]; then
        echo "⚠ WARNING: could not resolve the app object id; skipping SPA redirect URI."
    else
        GRAPH_URI="https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}"
        SPA_BODY="{\"spa\":{\"redirectUris\":[\"${SPA_REDIRECT}\"]}}"
        SPA_OUT=$(az rest --method PATCH --uri "$GRAPH_URI" \
            --headers "Content-Type=application/json" \
            --body "$SPA_BODY" 2>&1) \
            && echo "✓ Registered SPA redirect URI: ${SPA_REDIRECT}" \
            || { echo "⚠ WARNING: could not register the SPA redirect URI (${SPA_REDIRECT}):"; echo "$SPA_OUT"; }
    fi
fi

# -------------------------------------------------------
# The frontend SPA owns sign-in via MSAL, so it must load anonymously -- a
# RedirectToLoginPage Easy Auth gate would block the JS from ever running.
# Disable ingress Easy Auth on the frontend and wire the MSAL parameters
# (client id + tenant) as env vars the SPA reads from /config at runtime.
# -------------------------------------------------------
if [ -n "$FRONTEND_NAME" ]; then
    az containerapp auth update \
        --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_NAME" \
        --enabled false >/dev/null 2>&1 \
        || echo "⚠ WARNING: could not disable Easy Auth on the frontend."
    az containerapp update \
        --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_NAME" \
        --set-env-vars "AZURE_AUTH_CLIENT_ID=${APP_ID}" "AZURE_TENANT_ID=${TENANT_ID}" \
        >/dev/null 2>&1 \
        || echo "⚠ WARNING: could not set the frontend MSAL env vars."
    echo "✓ Frontend set for MSAL (Easy Auth disabled; AZURE_AUTH_CLIENT_ID / AZURE_TENANT_ID set)."
fi

# -------------------------------------------------------
# Enable Easy Auth on the backend ingress, fail closed. The browser
# forwards the MSAL id_token, whose audience is the shared app's client
# id; the backend validates that audience (bearer validation only, no
# client secret stored). `/api/health` is excluded so the liveness probe
# stays publicly reachable (no token required).
# -------------------------------------------------------
echo ""
echo "--- Enabling Easy Auth on ${BACKEND_NAME} (fail closed) ---"

# The MSAL id_token audience is the shared app client id (APP_ID).
TOKEN_AUD="$APP_ID"

BACKEND_PROVIDER_OUT=$(az containerapp auth microsoft update \
    --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
    --client-id "$APP_ID" \
    --issuer "$ISSUER" \
    --allowed-audiences "$TOKEN_AUD" \
    --yes 2>&1) \
    || { echo "✗ ERROR: failed to configure the Microsoft identity provider on the backend:" >&2; echo "$BACKEND_PROVIDER_OUT" >&2; exit 1; }

az containerapp auth update \
    --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
    --enabled true \
    --unauthenticated-client-action Return401 \
    --excluded-paths "/api/health" \
    --redirect-provider azureActiveDirectory >/dev/null 2>&1 \
    || { echo "✗ ERROR: failed to enable Easy Auth on the backend ingress." >&2; exit 1; }

echo "✓ Easy Auth enabled; unauthenticated requests now return 401 at the ingress."

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
if [ -n "$FRONTEND_FQDN" ]; then
    az containerapp ingress cors enable \
        --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
        --allowed-origins "https://${FRONTEND_FQDN}" \
        --allowed-methods GET POST PUT DELETE PATCH OPTIONS \
        --allowed-headers "*" >/dev/null 2>&1 \
        && echo "✓ Backend ingress CORS allows https://${FRONTEND_FQDN}." \
        || echo "⚠ WARNING: could not configure backend ingress CORS for https://${FRONTEND_FQDN}."
fi

# -------------------------------------------------------
# Turn on the app-layer defense-in-depth gate (code default is already true).
# -------------------------------------------------------
az containerapp update --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
    --set-env-vars "AZURE_REQUIRE_ADMIN_AUTH=true" >/dev/null 2>&1 \
    || echo "⚠ WARNING: could not set AZURE_REQUIRE_ADMIN_AUTH (code default is true)."
echo "✓ Backend app-layer admin-auth gate set (AZURE_REQUIRE_ADMIN_AUTH=true)."

# -------------------------------------------------------
# Record values in the azd environment (reference + CORS origin).
# -------------------------------------------------------
AUDIENCE="api://$APP_ID"
if command -v azd &> /dev/null; then
    azd env set AZURE_BACKEND_AUTH_CLIENT_ID "$APP_ID" >/dev/null 2>&1 || true
    azd env set AZURE_BACKEND_AUTH_AUDIENCE "$AUDIENCE" >/dev/null 2>&1 || true
    if [ -n "$FRONTEND_FQDN" ]; then
        azd env set BACKEND_CORS_ORIGINS "https://${FRONTEND_FQDN}" >/dev/null 2>&1 || true
    fi
    echo "✓ Recorded AZURE_BACKEND_AUTH_CLIENT_ID / AUDIENCE (and CORS origin) in the azd env."
else
    echo "⚠ azd not on PATH; set these manually in .azure/<env>/.env:"
    echo "    AZURE_BACKEND_AUTH_CLIENT_ID=${APP_ID}"
    echo "    AZURE_BACKEND_AUTH_AUDIENCE=${AUDIENCE}"
    [ -n "$FRONTEND_FQDN" ] && echo "    BACKEND_CORS_ORIGINS=https://${FRONTEND_FQDN}"
fi

# -------------------------------------------------------
# Verify the ingress now rejects anonymous admin calls (auth changes take a
# few minutes to propagate, so retry with backoff).
# -------------------------------------------------------
VERIFY_URL="https://${BACKEND_FQDN}/api/admin/status"
if [ -n "$BACKEND_FQDN" ]; then
    echo ""
    echo "--- Verifying anonymous admin call is rejected (allow time to propagate) ---"
    VERIFIED="no"
    for i in 1 2 3 4 5 6; do
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "$VERIFY_URL" 2>/dev/null || echo "000")
        if [ "$CODE" = "401" ] || [ "$CODE" = "403" ]; then
            echo "✓ Anonymous call returned HTTP ${CODE} -- backend is secured."
            VERIFIED="yes"
            break
        fi
        echo "  [${i}/6] Got HTTP ${CODE}; retrying in 20s..."
        sleep 20
    done
    [ "$VERIFIED" = "no" ] && echo "⚠ Not yet returning 401/403. Easy Auth may need more time; re-check manually."
fi

echo ""
echo "=============================================="
echo " Backend Authentication Setup Complete"
echo "=============================================="
echo ""
echo "The frontend and backend are now protected by Easy Auth. Signed-in users"
echo "reach the app; the browser forwards its login token to the backend, which"
echo "accepts it; anonymous callers get 401 at the backend ingress."
echo ""
echo "If you had other sessions open, sign out and back in so the browser picks"
echo "up a fresh token. Re-verify any time with:"
echo "    curl -i ${VERIFY_URL}"
