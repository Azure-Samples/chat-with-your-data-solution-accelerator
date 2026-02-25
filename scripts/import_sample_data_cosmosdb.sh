#!/bin/bash
set -euo pipefail

###############################################################################
# import_sample_data_cosmosdb.sh
#
# Imports sample data into Azure Search (CosmosDB-backed deployment).
# Uses the currently logged-in Azure user identity.
#
# The script auto-discovers the Azure Search service and Storage account
# from the given resource group, uploads a sample document to blob storage
# to trigger index creation, then populates the search index with sample data.
#
# Usage:
#   ./scripts/import_sample_data_cosmosdb.sh <RESOURCE_GROUP_NAME> [--waf]
#
# Options:
#   --waf   Enables public access temporarily for data import, then disables
#           it afterwards. Use for WAF deployments.
#
# Prerequisites:
#   - Azure CLI installed and logged in (`az login`)
#   - Python 3.8+ installed
#   - pip available
#   - jq installed
#   - curl installed
###############################################################################

# ──────────────────────────────────────────────────────────────────────────────
# Parse arguments
# ──────────────────────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "❌ Usage: $0 <RESOURCE_GROUP_NAME> [--waf]"
    echo "   Example: $0 my-resource-group"
    echo "   Example: $0 my-resource-group --waf"
    exit 1
fi

RESOURCE_GROUP_NAME="$1"
IS_WAF=false

# Check for --waf flag
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --waf)
            IS_WAF=true
            shift
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "   Usage: $0 <RESOURCE_GROUP_NAME> [--waf]"
            exit 1
            ;;
    esac
done

# Resolve the repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SEARCH_DATA_FILE="$REPO_ROOT/azure_search_data.json"
SAMPLE_DOC_FILE="$REPO_ROOT/data/PerksPlus.pdf"

# Detect Python command (python3 or python)
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ ERROR: Python not found. Please install Python 3.8+."
    exit 1
fi
echo "Using Python: $($PYTHON --version)"

# Check for required tools
for cmd in jq curl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "❌ ERROR: '$cmd' is required but not found. Please install it."
        exit 1
    fi
done

# ──────────────────────────────────────────────────────────────────────────────
# Validate input parameters
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Validating input parameters..."

if [[ ! "$RESOURCE_GROUP_NAME" =~ ^[a-zA-Z0-9._\(\)-]+$ ]] || [[ "$RESOURCE_GROUP_NAME" =~ \.$ ]]; then
    echo "❌ ERROR: RESOURCE_GROUP_NAME '$RESOURCE_GROUP_NAME' is invalid."
    echo "   Must contain only alphanumerics, periods, underscores, hyphens, and parentheses. Cannot end with period."
    exit 1
fi

if [[ ${#RESOURCE_GROUP_NAME} -gt 90 ]]; then
    echo "❌ ERROR: RESOURCE_GROUP_NAME '$RESOURCE_GROUP_NAME' exceeds 90 characters."
    exit 1
fi

if [[ ! -f "$SEARCH_DATA_FILE" ]]; then
    echo "❌ ERROR: Search data file not found at '$SEARCH_DATA_FILE'."
    exit 1
fi

if [[ ! -f "$SAMPLE_DOC_FILE" ]]; then
    echo "❌ ERROR: Sample document file not found at '$SAMPLE_DOC_FILE'."
    exit 1
fi

echo "✅ Input parameters validated."

# ──────────────────────────────────────────────────────────────────────────────
# Verify Azure CLI login
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Checking Azure CLI login status..."

if ! az account show &>/dev/null; then
    echo "❌ ERROR: Not logged in to Azure CLI. Please run 'az login' first."
    exit 1
fi

SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)
SUBSCRIPTION_NAME=$(az account show --query "name" -o tsv)
echo "✅ Logged in to Azure. Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# ──────────────────────────────────────────────────────────────────────────────
# Get current user details
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Fetching current user details..."

SIGNED_IN_USER_TYPE=$(az account show --query "user.type" -o tsv)
SIGNED_IN_USER_NAME=$(az account show --query "user.name" -o tsv)

if [[ "$SIGNED_IN_USER_TYPE" == "user" ]]; then
    USER_DISPLAY_NAME=$(az ad signed-in-user show --query "displayName" -o tsv)
    echo "✅ Signed in as user: $USER_DISPLAY_NAME ($SIGNED_IN_USER_NAME)"
elif [[ "$SIGNED_IN_USER_TYPE" == "servicePrincipal" ]]; then
    USER_DISPLAY_NAME=$(az ad sp show --id "$SIGNED_IN_USER_NAME" --query "displayName" -o tsv)
    echo "✅ Signed in as service principal: $USER_DISPLAY_NAME ($SIGNED_IN_USER_NAME)"
else
    echo "❌ ERROR: Unsupported login type: $SIGNED_IN_USER_TYPE"
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# Validate resource group exists
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Validating resource group '$RESOURCE_GROUP_NAME'..."

if ! az group show --name "$RESOURCE_GROUP_NAME" &>/dev/null; then
    echo "❌ ERROR: Resource group '$RESOURCE_GROUP_NAME' not found in subscription '$SUBSCRIPTION_NAME'."
    exit 1
fi

echo "✅ Resource group '$RESOURCE_GROUP_NAME' exists."

# ──────────────────────────────────────────────────────────────────────────────
# Discover Azure Search service in the resource group
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Discovering Azure Search service in resource group '$RESOURCE_GROUP_NAME'..."

SEARCH_SERVICES_JSON=$(az search service list --resource-group "$RESOURCE_GROUP_NAME" -o json 2>/dev/null || echo "[]")
SEARCH_SERVICE_COUNT=$(echo "$SEARCH_SERVICES_JSON" | jq 'length')

if [[ "$SEARCH_SERVICE_COUNT" -eq 0 ]]; then
    echo "❌ ERROR: No Azure Search service found in resource group '$RESOURCE_GROUP_NAME'."
    exit 1
elif [[ "$SEARCH_SERVICE_COUNT" -gt 1 ]]; then
    echo "⚠️  Multiple Azure Search services found. Using the first one."
fi

AZURE_SEARCH_SERVICE=$(echo "$SEARCH_SERVICES_JSON" | jq -r '.[0].name')
echo "✅ Found Azure Search service: $AZURE_SEARCH_SERVICE"

# ──────────────────────────────────────────────────────────────────────────────
# Discover Storage Account in the resource group
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Discovering Storage Account in resource group '$RESOURCE_GROUP_NAME'..."

STORAGE_ACCOUNTS_JSON=$(az storage account list --resource-group "$RESOURCE_GROUP_NAME" -o json 2>/dev/null || echo "[]")
STORAGE_ACCOUNT_COUNT=$(echo "$STORAGE_ACCOUNTS_JSON" | jq 'length')

if [[ "$STORAGE_ACCOUNT_COUNT" -eq 0 ]]; then
    echo "❌ ERROR: No Storage Account found in resource group '$RESOURCE_GROUP_NAME'."
    exit 1
elif [[ "$STORAGE_ACCOUNT_COUNT" -gt 1 ]]; then
    echo "⚠️  Multiple Storage Accounts found. Using the first one."
fi

AZURE_BLOB_ACCOUNT_NAME=$(echo "$STORAGE_ACCOUNTS_JSON" | jq -r '.[0].name')
echo "✅ Found Storage Account: $AZURE_BLOB_ACCOUNT_NAME"

# ──────────────────────────────────────────────────────────────────────────────
# Auto-detect WAF deployment if --waf not explicitly set
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$IS_WAF" == "false" ]]; then
    echo ""
    echo "🔍 Checking network access configuration..."

    SEARCH_PUBLIC_ACCESS=$(echo "$SEARCH_SERVICES_JSON" | jq -r '.[0].publicNetworkAccess // "enabled"')
    STORAGE_PUBLIC_ACCESS=$(echo "$STORAGE_ACCOUNTS_JSON" | jq -r '.[0].publicNetworkAccess // "Enabled"')

    if [[ "$SEARCH_PUBLIC_ACCESS" == "disabled" ]] || [[ "$STORAGE_PUBLIC_ACCESS" == "Disabled" ]]; then
        IS_WAF=true
        echo "🔒 Public network access is DISABLED — auto-detected as WAF deployment."
    else
        echo "🌐 Public network access is ENABLED — detected as Non-WAF deployment."
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# Define cleanup function to restore WAF state on exit
# ──────────────────────────────────────────────────────────────────────────────
WAF_ENABLED=false

cleanup() {
    local exit_code=$?
    if [[ "$IS_WAF" == "true" && "$WAF_ENABLED" == "true" ]]; then
        echo ""
        echo "🧹 Cleaning up — restoring WAF state..."

        # ========== Disable Public Access for Azure Search ==========
        echo "   Disabling public access for Azure Search service: $AZURE_SEARCH_SERVICE"

        IDENTITY_TYPE=$(az search service show \
            --name "$AZURE_SEARCH_SERVICE" \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --query "identity.type" -o tsv 2>/dev/null || echo "None")

        SEARCH_RESTORE_SUCCESS=false
        MAX_RETRIES=5
        RETRY_DELAY=30

        for attempt in $(seq 1 $MAX_RETRIES); do
            if [[ "$IDENTITY_TYPE" == *"UserAssigned"* ]]; then
                CURRENT_CONFIG=$(az search service show \
                    --name "$AZURE_SEARCH_SERVICE" \
                    --resource-group "$RESOURCE_GROUP_NAME" \
                    -o json)
                IDENTITY_BLOCK=$(echo "$CURRENT_CONFIG" | jq '.identity')
                PATCH_BODY=$(jq -n \
                    --argjson identity "$IDENTITY_BLOCK" \
                    '{
                      "properties": {
                        "publicNetworkAccess": "disabled"
                      },
                      "identity": $identity
                    }')

                if az rest --method PATCH \
                    --uri "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Search/searchServices/${AZURE_SEARCH_SERVICE}?api-version=2024-03-01-preview" \
                    --body "$PATCH_BODY" &>/dev/null; then
                    SEARCH_RESTORE_SUCCESS=true
                    break
                fi
            else
                if az search service update \
                    --name "$AZURE_SEARCH_SERVICE" \
                    --resource-group "$RESOURCE_GROUP_NAME" \
                    --public-access disabled &>/dev/null; then
                    SEARCH_RESTORE_SUCCESS=true
                    break
                fi
            fi

            if [ $attempt -lt $MAX_RETRIES ]; then
                sleep $RETRY_DELAY
                RETRY_DELAY=$((RETRY_DELAY * 2))
            fi
        done

        if [[ "$SEARCH_RESTORE_SUCCESS" == "true" ]]; then
            echo "   ✅ Public access disabled for Azure Search service."
        else
            echo "   ❌ Failed to disable public access for Azure Search service after $MAX_RETRIES attempts."
        fi

        # ========== Disable Public Access for Storage Account ==========
        echo "   Disabling public access for Storage Account: $AZURE_BLOB_ACCOUNT_NAME"

        az storage account update \
            --name "$AZURE_BLOB_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --public-network-access Disabled \
            --output none 2>/dev/null || true

        az storage account update \
            --name "$AZURE_BLOB_ACCOUNT_NAME" \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --default-action Deny \
            --output none 2>/dev/null || true

        echo "   ✅ Public access disabled for Storage Account."
        echo "✅ WAF state restored."
    fi

    exit $exit_code
}

# Register cleanup trap to run on EXIT (success or failure)
trap cleanup EXIT

# ──────────────────────────────────────────────────────────────────────────────
# Enable public access for WAF deployment
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$IS_WAF" == "true" ]]; then
    echo ""
    echo "🌐 Temporarily enabling public access for WAF deployment..."

    # ========== Enable Public Access for Azure Search ==========
    echo ""
    echo "📦 Configuring Azure Search service: $AZURE_SEARCH_SERVICE"

    IDENTITY_TYPE=$(az search service show \
        --name "$AZURE_SEARCH_SERVICE" \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --query "identity.type" -o tsv 2>/dev/null || echo "None")

    echo "   Current identity type: $IDENTITY_TYPE"

    MAX_RETRIES=5
    RETRY_DELAY=30
    SEARCH_SUCCESS=false

    for attempt in $(seq 1 $MAX_RETRIES); do
        echo "   Attempt $attempt of $MAX_RETRIES..."

        if [[ "$IDENTITY_TYPE" == *"UserAssigned"* ]]; then
            echo "   Using REST API to preserve UserAssigned identity configuration..."

            CURRENT_CONFIG=$(az search service show \
                --name "$AZURE_SEARCH_SERVICE" \
                --resource-group "$RESOURCE_GROUP_NAME" \
                -o json)

            IDENTITY_BLOCK=$(echo "$CURRENT_CONFIG" | jq '.identity')

            PATCH_BODY=$(jq -n \
                --argjson identity "$IDENTITY_BLOCK" \
                '{
                  "properties": {
                    "publicNetworkAccess": "enabled"
                  },
                  "identity": $identity
                }')

            if az rest --method PATCH \
                --uri "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Search/searchServices/${AZURE_SEARCH_SERVICE}?api-version=2024-03-01-preview" \
                --body "$PATCH_BODY" 2>&1; then
                echo "   ✅ Public access enabled for Azure Search service"
                SEARCH_SUCCESS=true
                break
            fi
        else
            if az search service update \
                --name "$AZURE_SEARCH_SERVICE" \
                --resource-group "$RESOURCE_GROUP_NAME" \
                --public-access enabled 2>&1; then
                echo "   ✅ Public access enabled for Azure Search service"
                SEARCH_SUCCESS=true
                break
            fi
        fi

        if [ $attempt -lt $MAX_RETRIES ]; then
            echo "   ⚠️ Update failed, retrying in ${RETRY_DELAY} seconds..."
            sleep $RETRY_DELAY
            RETRY_DELAY=$((RETRY_DELAY * 2))
        fi
    done

    if [[ "$SEARCH_SUCCESS" != "true" ]]; then
        echo "❌ Failed to enable public access for Azure Search after $MAX_RETRIES attempts"
        exit 1
    fi

    # ========== Enable Public Access for Storage Account ==========
    echo ""
    echo "📦 Configuring Storage Account: $AZURE_BLOB_ACCOUNT_NAME"

    az storage account update \
        --name "$AZURE_BLOB_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --public-network-access Enabled \
        --output none

    az storage account update \
        --name "$AZURE_BLOB_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --default-action Allow \
        --output none

    echo "   ✅ Public access enabled for Storage Account"

    WAF_ENABLED=true

    echo ""
    echo "⏳ Waiting 5 minutes for WAF network changes to propagate..."
    sleep 300
    echo "✅ Propagation wait complete."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Upload sample document to Blob Storage to trigger index creation
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📤 Uploading sample document to blob storage to trigger index creation..."

STORAGE_KEY=$(az storage account keys list \
    --account-name "$AZURE_BLOB_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query '[0].value' -o tsv)

az storage blob upload \
    --account-name "$AZURE_BLOB_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --container-name "documents" \
    --name "PerksPlus.pdf" \
    --file "$SAMPLE_DOC_FILE" \
    --overwrite

echo "✅ Document uploaded to blob storage."

# ──────────────────────────────────────────────────────────────────────────────
# Get Azure Search admin key
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔑 Retrieving Azure Search admin key..."

AZURE_SEARCH_KEY=$(az search admin-key show \
    --service-name "$AZURE_SEARCH_SERVICE" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query primaryKey -o tsv)

echo "✅ Azure Search admin key retrieved."

# ──────────────────────────────────────────────────────────────────────────────
# Wait for index creation and detect index name
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Waiting for index to be auto-created and detecting it..."
echo "   This may take a few minutes as the document is processed..."

AZURE_SEARCH_INDEX=""

for i in $(seq 1 30); do
    echo "   Checking for indexes (attempt $i/30)..."

    INDEXES_RESPONSE=$(curl -s \
        "https://${AZURE_SEARCH_SERVICE}.search.windows.net/indexes?\$select=name&api-version=2024-07-01" \
        -H "api-key: ${AZURE_SEARCH_KEY}")

    INDEX_COUNT=$(echo "$INDEXES_RESPONSE" | jq -r '.value | length' 2>/dev/null || echo "0")

    if [[ "$INDEX_COUNT" -gt 0 ]]; then
        AZURE_SEARCH_INDEX=$(echo "$INDEXES_RESPONSE" | jq -r '.value[0].name')
        echo "   ✅ Found index: '$AZURE_SEARCH_INDEX'"
        break
    fi

    if [[ $i -eq 30 ]]; then
        echo "❌ No index found after 15 minutes."
        exit 1
    fi

    echo "   No indexes found yet, waiting 30 seconds..."
    sleep 30
done

echo "✅ Using index: $AZURE_SEARCH_INDEX"

# ──────────────────────────────────────────────────────────────────────────────
# Install Python dependencies
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📦 Installing Python dependencies..."
pip install requests --quiet

# ──────────────────────────────────────────────────────────────────────────────
# Populate Azure Search index with sample data
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📥 Populating Azure Search index: $AZURE_SEARCH_INDEX"

export AZURE_SEARCH_SERVICE
export AZURE_SEARCH_INDEX
export AZURE_SEARCH_KEY

$PYTHON - "$SEARCH_DATA_FILE" <<'PYTHON_SCRIPT'
import requests
import json
import os
import sys

SEARCH_SERVICE = os.environ.get("AZURE_SEARCH_SERVICE")
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX")
API_KEY = os.environ.get("AZURE_SEARCH_KEY")
DATA_FILE = sys.argv[1]

# Use stable API version
API_VERSION = "2024-07-01"

# Search API endpoint
ENDPOINT = f"https://{SEARCH_SERVICE}.search.windows.net/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"
HEADERS = {
    "Content-Type": "application/json",
    "api-key": API_KEY
}

print(f"  Azure Search Service : {SEARCH_SERVICE}")
print(f"  Index Name           : {INDEX_NAME}")
print(f"  Data File            : {DATA_FILE}")

# Load exported data
with open(DATA_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

# Format for Azure Search bulk upload
payload = {
    "value": [{"@search.action": "upload", **doc} for doc in documents]
}

print(f"  Uploading {len(documents)} documents to index '{INDEX_NAME}'...")

# Send data to Azure Search
response = requests.post(ENDPOINT, headers=HEADERS, json=payload)

if response.status_code in [200, 207]:
    result = response.json()
    success_count = sum(1 for item in result.get('value', []) if item.get('status', False))
    print(f"  ✅ Import completed! {success_count}/{len(documents)} documents uploaded successfully.")
else:
    print(f"  ❌ Failed to import data: {response.status_code}, {response.text}")
    sys.exit(1)
PYTHON_SCRIPT

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Import Sample Data (CosmosDB) — Complete"
echo "═══════════════════════════════════════════════════════════════"
echo "  Resource Group        : $RESOURCE_GROUP_NAME"
echo "  Azure Search Service  : $AZURE_SEARCH_SERVICE"
echo "  Azure Search Index    : $AZURE_SEARCH_INDEX"
echo "  Storage Account       : $AZURE_BLOB_ACCOUNT_NAME"
echo "  WAF Deployment        : $IS_WAF"
echo "  User                  : $USER_DISPLAY_NAME ($SIGNED_IN_USER_NAME)"
echo "═══════════════════════════════════════════════════════════════"
