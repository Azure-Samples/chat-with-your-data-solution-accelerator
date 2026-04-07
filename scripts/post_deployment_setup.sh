#!/bin/bash
set -e

# Prevent Git Bash (MSYS) from mangling Azure resource ID paths like /subscriptions/...
export MSYS_NO_PATHCONV=1

# Post-deployment setup script for Chat With Your Data Solution Accelerator.
# Run this manually after 'azd provision' / 'azd up' completes.
#
# This single script performs two tasks:
#   1. Sets the Function App client key (retrieved from Key Vault).
#   2. Creates PostgreSQL tables (if a PostgreSQL server exists in the resource group).
#
# If private networking (WAF) is enabled, the script temporarily enables public access
# on Key Vault and PostgreSQL, performs the operations, then restores the original state.
#
# Usage: ./scripts/post_deployment_setup.sh <resource-group-name>

if [ -z "$1" ]; then
    echo "Usage: $0 <resource-group-name>"
    exit 1
fi

RESOURCE_GROUP="$1"

echo "=============================================="
echo " Post-Deployment Setup"
echo " Resource Group: ${RESOURCE_GROUP}"
echo "=============================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"

# Track resources that need public access restored to Disabled
RESTORE_KV_NAME=""
RESTORE_PG_NAME=""

restore_network_access() {
    if [ -n "$RESTORE_KV_NAME" ]; then
        echo "✓ Disabling public access on Key Vault '${RESTORE_KV_NAME}'..."
        az keyvault update --name "$RESTORE_KV_NAME" --resource-group "$RESOURCE_GROUP" --public-network-access Disabled > /dev/null 2>&1 || echo "⚠ WARNING: Failed to disable public access on Key Vault. Please disable manually."
    fi
    if [ -n "$RESTORE_PG_NAME" ]; then
        echo "✓ Disabling public access on PostgreSQL '${RESTORE_PG_NAME}'..."
        az postgres flexible-server update --resource-group "$RESOURCE_GROUP" --name "$RESTORE_PG_NAME" --public-access Disabled > /dev/null 2>&1 || echo "⚠ WARNING: Failed to disable public access on PostgreSQL. Please disable manually."
    fi
}

# -------------------------------------------------------
# STEP 1 — Set Function App Client Key
# -------------------------------------------------------
echo ""
echo "--- Step 1: Set Function App Client Key ---"

FUNCTION_APP_NAME=$(az functionapp list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)

if [ -z "$FUNCTION_APP_NAME" ]; then
    echo "No function apps found in resource group '${RESOURCE_GROUP}'. Skipping function key setup."
else
    echo "✓ Discovered function app: ${FUNCTION_APP_NAME}"

    KEY_VAULT_NAME=$(az keyvault list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)
    if [ -z "$KEY_VAULT_NAME" ]; then
        echo "⚠ WARNING: No Key Vault found. Skipping function key setup."
    else
        echo "✓ Discovered Key Vault: ${KEY_VAULT_NAME}"

        # Ensure the current user has 'Key Vault Secrets User' role on the Key Vault
        CURRENT_USER_OID=$(az ad signed-in-user show --query "id" -o tsv 2>/dev/null || true)
        if [ -n "$CURRENT_USER_OID" ]; then
            KV_RESOURCE_ID=$(az keyvault show --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv 2>/dev/null || true)
            if [ -n "$KV_RESOURCE_ID" ]; then
                KV_SECRETS_USER_ROLE_ID="4633458b-17de-408a-b874-0445c86b69e6"
                EXISTING_ASSIGNMENT=$(az role assignment list --assignee "$CURRENT_USER_OID" --role "$KV_SECRETS_USER_ROLE_ID" --scope "$KV_RESOURCE_ID" --query "[0].id" -o tsv 2>/dev/null || true)
                if [ -z "$EXISTING_ASSIGNMENT" ]; then
                    echo "✓ Assigning 'Key Vault Secrets User' role to current user on Key Vault..."
                    if az role assignment create --assignee-object-id "$CURRENT_USER_OID" --assignee-principal-type User --role "$KV_SECRETS_USER_ROLE_ID" --scope "$KV_RESOURCE_ID" > /dev/null 2>&1; then
                        echo "✓ Role assigned. Waiting 30s for propagation..."
                        sleep 30
                    else
                        echo "⚠ WARNING: Failed to assign Key Vault Secrets User role. You may not have Owner/User Access Administrator permissions."
                    fi
                else
                    echo "✓ Current user already has 'Key Vault Secrets User' role on Key Vault."
                fi
            fi
        else
            echo "⚠ WARNING: Could not determine current user OID. Skipping Key Vault role assignment."
        fi

        # Check if Key Vault public access is disabled (WAF/private networking)
        KV_PUBLIC_ACCESS=$(az keyvault show --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.publicNetworkAccess" -o tsv 2>/dev/null || true)
        if [ "$KV_PUBLIC_ACCESS" = "Disabled" ]; then
            echo "Key Vault has public access disabled (private networking detected)."
            echo "✓ Temporarily enabling public access on Key Vault '${KEY_VAULT_NAME}'..."
            if ! az keyvault update --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" --public-network-access Enabled > /dev/null 2>&1; then
                echo "✗ ERROR: Failed to enable public access on Key Vault. Cannot proceed." >&2
                exit 1
            fi
            RESTORE_KV_NAME="$KEY_VAULT_NAME"
            echo "Waiting for Key Vault network change to propagate..."
            sleep 30
        fi

        echo "✓ Retrieving function key from Key Vault..."
        FUNCTION_KEY=$(az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "FUNCTION-KEY" --query "value" -o tsv 2>/dev/null || true)
        if [ -z "$FUNCTION_KEY" ]; then
            echo "✗ ERROR: Failed to retrieve 'FUNCTION-KEY' secret from Key Vault '${KEY_VAULT_NAME}'." >&2
            restore_network_access
            exit 1
        fi

        # Wait for function app to be running
        echo "Waiting for function app to be ready..."
        MAX_RETRIES=30
        RETRY_INTERVAL=20
        for i in $(seq 1 $MAX_RETRIES); do
            STATE=$(az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv 2>/dev/null || true)
            if [ "$STATE" = "Running" ]; then
                echo "Function app is running."
                break
            fi
            echo "  [${i}/${MAX_RETRIES}] Function app not running yet. Retrying in ${RETRY_INTERVAL}s..."
            sleep $RETRY_INTERVAL
        done

        # Set the function key via REST API
        echo "✓ Setting function key 'ClientKey' on '${FUNCTION_APP_NAME}'..."
        SUBSCRIPTION_ID=$(az account show --query "id" -o tsv | tr -d '\r')
        URI="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${FUNCTION_APP_NAME}/host/default/functionKeys/clientKey?api-version=2023-01-01"
        BODY="{\"properties\":{\"name\":\"ClientKey\",\"value\":\"${FUNCTION_KEY}\"}}"

        if ! az rest --method put --uri "$URI" --body "$BODY" > /dev/null 2>&1; then
            echo "✗ ERROR: Failed to set function key on '${FUNCTION_APP_NAME}'." >&2
            restore_network_access
            exit 1
        fi
        echo "✓ Function key set successfully."
    fi
fi

# -------------------------------------------------------
# STEP 2 — Create PostgreSQL Tables (if applicable)
# -------------------------------------------------------
echo ""
echo "--- Step 2: Create PostgreSQL Tables ---"

SERVER_FQDN=$(az postgres flexible-server list --resource-group "$RESOURCE_GROUP" --query "[0].fullyQualifiedDomainName" -o tsv 2>/dev/null || true)

if [ -z "$SERVER_FQDN" ]; then
    echo "No PostgreSQL Flexible Server found in resource group. Skipping table creation."
else
    SERVER_NAME=$(echo "$SERVER_FQDN" | cut -d'.' -f1)
    echo "✓ Discovered PostgreSQL server: ${SERVER_NAME} (${SERVER_FQDN})"

    # Check if PostgreSQL public access is disabled (WAF/private networking)
    PG_PUBLIC_ACCESS=$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" --name "$SERVER_NAME" --query "network.publicNetworkAccess" -o tsv 2>/dev/null || true)
    if [ "$PG_PUBLIC_ACCESS" = "Disabled" ]; then
        echo "PostgreSQL has public access disabled (private networking detected)."
        echo "✓ Temporarily enabling public access on PostgreSQL '${SERVER_NAME}'..."
        if ! az postgres flexible-server update --resource-group "$RESOURCE_GROUP" --name "$SERVER_NAME" --public-access Enabled > /dev/null 2>&1; then
            echo "✗ ERROR: Failed to enable public access on PostgreSQL. Cannot proceed." >&2
            restore_network_access
            exit 1
        fi
        RESTORE_PG_NAME="$SERVER_NAME"
        echo "Waiting for PostgreSQL network change to propagate..."
        sleep 30
    fi

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL server to be ready..."
    MAX_RETRIES=30
    RETRY_INTERVAL=20
    for i in $(seq 1 $MAX_RETRIES); do
        PG_STATE=$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" --name "$SERVER_NAME" --query "state" -o tsv 2>/dev/null || true)
        if [ "$PG_STATE" = "Ready" ]; then
            echo "PostgreSQL server is ready."
            break
        fi
        echo "  [${i}/${MAX_RETRIES}] Server not ready (state: ${PG_STATE}). Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done

    # Add firewall rule for current machine
    PUBLIC_IP=$(curl -s https://api.ipify.org)
    echo "✓ Adding temporary firewall rule for IP ${PUBLIC_IP}..."
    az postgres flexible-server firewall-rule create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$SERVER_NAME" \
        --rule-name "AllowPostDeploySetup" \
        --start-ip-address "$PUBLIC_IP" \
        --end-ip-address "$PUBLIC_IP" > /dev/null 2>&1

    # Get current user info for local Entra auth to PostgreSQL
    CURRENT_USER_UPN=$(az ad signed-in-user show --query "userPrincipalName" -o tsv 2>/dev/null || true)
    CURRENT_USER_OID=$(az ad signed-in-user show --query "id" -o tsv 2>/dev/null || true)
    if [ -z "$CURRENT_USER_UPN" ] || [ -z "$CURRENT_USER_OID" ]; then
        echo "✗ ERROR: Could not determine current signed-in user. Ensure you are logged in with 'az login'." >&2
        restore_network_access
        exit 1
    fi
    echo "✓ Current user: ${CURRENT_USER_UPN} (${CURRENT_USER_OID})"

    # Ensure current user is a PostgreSQL Entra administrator
    EXISTING_ADMINS=$(az postgres flexible-server ad-admin list --resource-group "$RESOURCE_GROUP" --server-name "$SERVER_NAME" --query "[].objectId" -o tsv 2>/dev/null || true)
    IS_ADMIN=false
    ADDED_PG_ADMIN=false
    if [ -n "$EXISTING_ADMINS" ]; then
        for ADMIN_OID in $EXISTING_ADMINS; do
            if [ "$(echo "$ADMIN_OID" | tr -d '[:space:]')" = "$CURRENT_USER_OID" ]; then
                IS_ADMIN=true
                break
            fi
        done
    fi
    if [ "$IS_ADMIN" = "false" ]; then
        echo "✓ Adding current user as PostgreSQL Entra administrator..."
        if az postgres flexible-server ad-admin create \
            --resource-group "$RESOURCE_GROUP" \
            --server-name "$SERVER_NAME" \
            --display-name "$CURRENT_USER_UPN" \
            --object-id "$CURRENT_USER_OID" \
            --type User > /dev/null 2>&1; then
            ADDED_PG_ADMIN=true
            echo "✓ PostgreSQL admin added. Waiting 60s for propagation..."
            sleep 60
        else
            echo "⚠ WARNING: Failed to add current user as PostgreSQL admin. Table creation may fail."
        fi
    else
        echo "✓ Current user is already a PostgreSQL Entra administrator."
    fi

    # Ensure firewall rule cleanup on exit (along with network restore)
    cleanup() {
        # Remove temporary PostgreSQL admin if we added it
        if [ "$ADDED_PG_ADMIN" = "true" ]; then
            echo "✓ Removing temporary PostgreSQL Entra admin for current user..."
            az postgres flexible-server ad-admin delete \
                --resource-group "$RESOURCE_GROUP" \
                --server-name "$SERVER_NAME" \
                --object-id "$CURRENT_USER_OID" \
                --yes 2>/dev/null || true
        fi
        echo "✓ Removing temporary firewall rule..."
        az postgres flexible-server firewall-rule delete \
            --resource-group "$RESOURCE_GROUP" \
            --name "$SERVER_NAME" \
            --rule-name "AllowPostDeploySetup" \
            --yes 2>/dev/null || true
        restore_network_access
    }
    trap cleanup EXIT

    # Install Python dependencies
    REQUIREMENTS_FILE="${SCRIPT_DIR}/data_scripts/requirements.txt"
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "✓ Installing Python dependencies..."
        pip install -r "$REQUIREMENTS_FILE"
    fi

    echo "✓ Creating tables..."
    python "$SCRIPT_DIR/data_scripts/setup_postgres_tables.py" "$SERVER_FQDN" "$CURRENT_USER_UPN"
    echo "✓ PostgreSQL table creation completed."
fi

# -------------------------------------------------------
# STEP 3 — Restore private networking (if no PostgreSQL trap set it)
# -------------------------------------------------------
# If no PostgreSQL server was found, the trap won't fire, so restore here
if [ -z "$SERVER_FQDN" ]; then
    restore_network_access
fi

echo ""
echo "=============================================="
echo " Post-Deployment Setup Complete"
echo "=============================================="
