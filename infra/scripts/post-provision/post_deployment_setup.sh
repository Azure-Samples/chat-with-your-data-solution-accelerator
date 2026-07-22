#!/bin/bash
set -e

# Prevent Git Bash (MSYS) from mangling Azure resource ID paths
export MSYS_NO_PATHCONV=1

# Post-deployment setup script for v2.
# Discovers resources from the resource group, handles WAF/private networking
# (temporarily enables public access), sets env vars, delegates to post_provision.py,
# then restores the original network state.
#
# Usage: ./infra/scripts/post-provision/post_deployment_setup.sh <resource-group-name>

if [ -z "$1" ]; then
    # Try to read from .azure/<env>/.env file
    # Script is at infra/scripts/post-provision/ — go up 3 dirs from script dir to reach repo root
    SCRIPT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
    AZURE_DIR="$SCRIPT_ROOT/.azure"
    if [ -d "$AZURE_DIR" ]; then
        ENV_FILE=$(find "$AZURE_DIR" -name ".env" -type f 2>/dev/null | head -1)
        if [ -n "$ENV_FILE" ]; then
            RESOURCE_GROUP=$(grep '^AZURE_RESOURCE_GROUP=' "$ENV_FILE" | sed 's/^AZURE_RESOURCE_GROUP=//;s/^"//;s/"$//')
        fi
    fi
    # Try AZURE_RESOURCE_GROUP env var
    if [ -z "$RESOURCE_GROUP" ]; then
        RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
    fi
    # Prompt as last resort
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
echo " Post-Deployment Setup (v2)"
echo " Resource Group: ${RESOURCE_GROUP}"
echo "=============================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"

# -------------------------------------------------------
# Track resources that need public access restored
# -------------------------------------------------------
RESTORE_PG_NAME=""
SERVER_NAME=""

cleanup() {
    # Remove temporary firewall rule
    if [ -n "$SERVER_NAME" ]; then
        echo "✓ Removing temporary firewall rule..."
        az postgres flexible-server firewall-rule delete \
            --resource-group "$RESOURCE_GROUP" \
            --server-name "$SERVER_NAME" \
            --name "AllowPostDeploySetup" \
            --yes 2>/dev/null || true
    fi
    # Restore public access to Disabled on PostgreSQL
    if [ -n "$RESTORE_PG_NAME" ]; then
        echo "✓ Disabling public access on PostgreSQL '${RESTORE_PG_NAME}'..."
        az postgres flexible-server update --resource-group "$RESOURCE_GROUP" \
            --name "$RESTORE_PG_NAME" --public-access Disabled > /dev/null 2>&1 \
            || echo "⚠ WARNING: Failed to disable public access on PostgreSQL. Please disable manually."
    fi
}
trap cleanup EXIT

# -------------------------------------------------------
# Discover resources and export env vars for post_provision.py
# -------------------------------------------------------
export AZURE_RESOURCE_GROUP="$RESOURCE_GROUP"

# PostgreSQL
SERVER_FQDN=$(az postgres flexible-server list --resource-group "$RESOURCE_GROUP" \
    --query "[0].fullyQualifiedDomainName" -o tsv 2>/dev/null || true)
if [ -n "$SERVER_FQDN" ]; then
    SERVER_NAME=$(echo "$SERVER_FQDN" | cut -d'.' -f1)
    export AZURE_POSTGRES_HOST="$SERVER_FQDN"
    export AZURE_POSTGRES_NAME="$SERVER_NAME"
    export AZURE_DB_TYPE="postgresql"
    # Clear any stale CosmosDB-mode vars from previous runs
    export AZURE_AI_SEARCH_ENDPOINT=""
    echo "✓ Discovered PostgreSQL: ${SERVER_NAME} (${SERVER_FQDN})"

    # --- WAF / Private Networking handling ---
    PG_PUBLIC_ACCESS=$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" \
        --name "$SERVER_NAME" --query "network.publicNetworkAccess" -o tsv 2>/dev/null || true)

    if [ "$PG_PUBLIC_ACCESS" = "Disabled" ]; then
        echo "PostgreSQL has public access disabled (private networking detected)."
        echo "✓ Temporarily enabling public access on PostgreSQL '${SERVER_NAME}'..."
        PG_ERR=$(az postgres flexible-server update --resource-group "$RESOURCE_GROUP" \
            --name "$SERVER_NAME" --public-access Enabled 2>&1) || true
        if echo "$PG_ERR" | grep -qi "error"; then
            echo "✗ ERROR: Failed to enable public access on PostgreSQL." >&2
            echo "  $PG_ERR" >&2
            exit 1
        fi
        RESTORE_PG_NAME="$SERVER_NAME"
        echo "Waiting for PostgreSQL network change to propagate..."
        sleep 30
    fi

    # Wait for PostgreSQL server to be ready (it enters "Updating" state
    # after public access change and won't accept connections until "Ready")
    echo "Waiting for PostgreSQL server to be ready..."
    MAX_RETRIES=30
    RETRY_INTERVAL=30
    for i in $(seq 1 $MAX_RETRIES); do
        PG_STATE=$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" \
            --name "$SERVER_NAME" --query "state" -o tsv 2>/dev/null || true)
        if [ "$PG_STATE" = "Ready" ]; then
            echo "PostgreSQL server is ready."
            break
        fi
        echo "  [${i}/${MAX_RETRIES}] Server not ready (state: ${PG_STATE}). Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done

    # Add temporary firewall rule for deployer's IP
    PUBLIC_IP=$(curl -s https://api.ipify.org)
    if [ -n "$PUBLIC_IP" ]; then
        echo "✓ Adding temporary firewall rule for IP ${PUBLIC_IP}..."
        az postgres flexible-server firewall-rule create \
            --resource-group "$RESOURCE_GROUP" \
            --server-name "$SERVER_NAME" \
            --name "AllowPostDeploySetup" \
            --start-ip-address "$PUBLIC_IP" \
            --end-ip-address "$PUBLIC_IP" 2>&1 || echo "⚠ WARNING: Firewall rule creation may have failed."
    fi
else
    export AZURE_DB_TYPE="cosmosdb"
    echo "✓ No PostgreSQL found; assuming CosmosDB mode."

    # AI Search (CosmosDB mode only — PostgreSQL uses pgvector for indexing)
    SEARCH_NAME=$(az search service list --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" -o tsv 2>/dev/null || true)
    if [ -n "$SEARCH_NAME" ]; then
        export AZURE_AI_SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"
        echo "✓ Discovered AI Search: ${SEARCH_NAME}"
    fi
fi

# OpenAI / AI Services (for knowledge base seed)
AI_SERVICES_ENDPOINT=$(az cognitiveservices account list --resource-group "$RESOURCE_GROUP" \
    --query "[?kind=='AIServices' || kind=='OpenAI'] | [0].properties.endpoint" -o tsv 2>/dev/null || true)
if [ -n "$AI_SERVICES_ENDPOINT" ]; then
    export AZURE_AI_SERVICES_ENDPOINT="$AI_SERVICES_ENDPOINT"
    export AZURE_OPENAI_ENDPOINT="$AI_SERVICES_ENDPOINT"
    echo "✓ Discovered AI Services: ${AI_SERVICES_ENDPOINT}"
fi

# GPT deployment (first deployment that isn't an embedding model)
GPT_DEPLOYMENT=$(az cognitiveservices account deployment list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$(az cognitiveservices account list --resource-group "$RESOURCE_GROUP" \
        --query "[?kind=='AIServices' || kind=='OpenAI'] | [0].name" -o tsv 2>/dev/null)" \
    --query "[?contains(properties.model.name,'gpt') || contains(properties.model.name,'o1') || contains(properties.model.name,'o3') || contains(properties.model.name,'o4-mini')] | [0].name" \
    -o tsv 2>/dev/null || true)
if [ -n "$GPT_DEPLOYMENT" ]; then
    export AZURE_OPENAI_GPT_DEPLOYMENT="$GPT_DEPLOYMENT"
    echo "✓ Discovered GPT deployment: ${GPT_DEPLOYMENT}"
fi

# Fallback for BYO / cross-subscription Foundry: the OpenAI account and GPT
# model live outside this resource group, so the in-RG lookups above find
# nothing. Read the authoritative endpoint and deployment the backend
# container app was deployed with.
if [ -z "$AI_SERVICES_ENDPOINT" ] || [ -z "$GPT_DEPLOYMENT" ]; then
    BACKEND_NAME=$(az containerapp list --resource-group "$RESOURCE_GROUP" \
        --query "[?contains(name,'backend')] | [0].name" -o tsv 2>/dev/null || true)
    if [ -n "$BACKEND_NAME" ]; then
        if [ -z "$AI_SERVICES_ENDPOINT" ]; then
            AI_SERVICES_ENDPOINT=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
                --query "properties.template.containers[0].env[?name=='AZURE_OPENAI_ENDPOINT'].value | [0]" -o tsv 2>/dev/null || true)
            if [ -n "$AI_SERVICES_ENDPOINT" ]; then
                export AZURE_AI_SERVICES_ENDPOINT="$AI_SERVICES_ENDPOINT"
                export AZURE_OPENAI_ENDPOINT="$AI_SERVICES_ENDPOINT"
                echo "✓ Discovered AI Services from backend app '${BACKEND_NAME}': ${AI_SERVICES_ENDPOINT}"
            fi
        fi
        if [ -z "$GPT_DEPLOYMENT" ]; then
            GPT_DEPLOYMENT=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_NAME" \
                --query "properties.template.containers[0].env[?name=='AZURE_OPENAI_GPT_DEPLOYMENT'].value | [0]" -o tsv 2>/dev/null || true)
            if [ -n "$GPT_DEPLOYMENT" ]; then
                export AZURE_OPENAI_GPT_DEPLOYMENT="$GPT_DEPLOYMENT"
                echo "✓ Discovered GPT deployment from backend app '${BACKEND_NAME}': ${GPT_DEPLOYMENT}"
            fi
        fi
    fi
fi

# Deployer UPN
DEPLOYER_UPN=$(az ad signed-in-user show --query "userPrincipalName" -o tsv 2>/dev/null || true)
if [ -n "$DEPLOYER_UPN" ]; then
    export AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME="$DEPLOYER_UPN"
fi

echo ""
echo "--- Running post_provision.py ---"
echo ""

# Run the Python script (uses uv if available, falls back to python)
if command -v uv &> /dev/null; then
    uv run python "$SCRIPT_DIR/post_provision.py"
elif command -v python3 &> /dev/null; then
    python3 "$SCRIPT_DIR/post_provision.py"
else
    python "$SCRIPT_DIR/post_provision.py"
fi

echo ""
echo "=============================================="
echo " Post-Deployment Setup Complete"
echo "=============================================="
