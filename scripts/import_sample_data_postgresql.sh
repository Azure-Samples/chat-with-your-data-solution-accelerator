#!/bin/bash
set -euo pipefail

###############################################################################
# import_sample_data_postgresql.sh
#
# Imports sample data from exported_data_vector_score.csv into the PostgreSQL
# vector_store table. Uses the currently logged-in Azure user identity.
#
# Usage:
#   ./scripts/import_sample_data_postgresql.sh <RESOURCE_GROUP_NAME>
#
# Prerequisites:
#   - Azure CLI installed and logged in (`az login`)
#   - Python 3.8+ installed
#   - pip available
###############################################################################

# ──────────────────────────────────────────────────────────────────────────────
# Parse arguments
# ──────────────────────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "❌ Usage: $0 <RESOURCE_GROUP_NAME>"
    echo "   Example: $0 my-resource-group"
    exit 1
fi

RESOURCE_GROUP_NAME="$1"

# Resolve the repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CSV_FILE="$REPO_ROOT/exported_data_vector_score.csv"

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

# ──────────────────────────────────────────────────────────────────────────────
# Validate input parameters
# ──────────────────────────────────────────────────────────────────────────────
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

if [[ ! -f "$CSV_FILE" ]]; then
    echo "❌ ERROR: CSV file not found at '$CSV_FILE'."
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
    # Interactive user login
    USER_OBJECT_ID=$(az ad signed-in-user show --query "id" -o tsv)
    USER_DISPLAY_NAME=$(az ad signed-in-user show --query "displayName" -o tsv)
    USER_PRINCIPAL_TYPE="User"
    echo "✅ Signed in as user: $USER_DISPLAY_NAME ($SIGNED_IN_USER_NAME)"
elif [[ "$SIGNED_IN_USER_TYPE" == "servicePrincipal" ]]; then
    # Service principal login
    USER_OBJECT_ID=$(az ad sp show --id "$SIGNED_IN_USER_NAME" --query "id" -o tsv)
    USER_DISPLAY_NAME=$(az ad sp show --id "$SIGNED_IN_USER_NAME" --query "displayName" -o tsv)
    USER_PRINCIPAL_TYPE="ServicePrincipal"
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
# Discover PostgreSQL Flexible Server in the resource group
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Discovering PostgreSQL Flexible Server in resource group '$RESOURCE_GROUP_NAME'..."

PG_SERVERS_JSON=$(az postgres flexible-server list --resource-group "$RESOURCE_GROUP_NAME" -o json 2>/dev/null || echo "[]")
PG_SERVER_COUNT=$(echo "$PG_SERVERS_JSON" | $PYTHON -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [[ "$PG_SERVER_COUNT" -eq 0 ]]; then
    echo "❌ ERROR: No PostgreSQL Flexible Server found in resource group '$RESOURCE_GROUP_NAME'."
    exit 1
elif [[ "$PG_SERVER_COUNT" -gt 1 ]]; then
    echo "⚠️  Multiple PostgreSQL Flexible Servers found. Using the first one."
fi

PG_SERVER_NAME=$(echo "$PG_SERVERS_JSON" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)[0]['name'])")
PG_FQDN=$(echo "$PG_SERVERS_JSON" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)[0]['fullyQualifiedDomainName'])")

echo "✅ Found PostgreSQL server: $PG_SERVER_NAME ($PG_FQDN)"

# ──────────────────────────────────────────────────────────────────────────────
# Detect WAF deployment (public access disabled)
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔍 Checking network access configuration..."

PUBLIC_ACCESS=$(echo "$PG_SERVERS_JSON" | $PYTHON -c "
import sys, json
server = json.load(sys.stdin)[0]
network = server.get('network', {})
pa = network.get('publicNetworkAccess', 'Unknown')
print(pa)
")

IS_WAF=false
if [[ "$PUBLIC_ACCESS" == "Disabled" ]]; then
    IS_WAF=true
    echo "🔒 Public network access is DISABLED — detected as WAF deployment."
else
    echo "🌐 Public network access is ENABLED — detected as Non-WAF deployment."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Add firewall rule for current machine's IP & handle WAF public access
# ──────────────────────────────────────────────────────────────────────────────

# Get the current public IP of this machine
echo ""
echo "🌐 Detecting current public IP address..."
PUBLIC_IP=$(curl -s https://api.ipify.org)
echo "   Detected public IP: $PUBLIC_IP"

FIREWALL_RULE_ADDED=false

# Define cleanup function to remove firewall rule and restore WAF state
cleanup() {
    echo ""
    echo "🧹 Cleaning up temporary firewall changes..."

    if [[ "$FIREWALL_RULE_ADDED" == "true" ]]; then
        echo "   Removing firewall rule 'AllowImportScriptAccess'..."
        az postgres flexible-server firewall-rule delete \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --name "$PG_SERVER_NAME" \
            --rule-name "AllowImportScriptAccess" \
            --yes 2>/dev/null || true
        echo "   ✅ Firewall rule removed."
    fi

    if [[ "$IS_WAF" == "true" ]]; then
        echo "   Disabling public network access (restoring WAF state)..."
        az postgres flexible-server update \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --name "$PG_SERVER_NAME" \
            --public-access Disabled 2>/dev/null || true
        echo "   ✅ Public access disabled."
    fi

    echo "✅ Cleanup complete."
}

# Register cleanup trap to run on EXIT (success or failure)
trap cleanup EXIT

if [[ "$IS_WAF" == "true" ]]; then
    echo ""
    echo "🌐 Temporarily enabling public access for WAF deployment..."

    echo "   Enabling public network access..."
    az postgres flexible-server update \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --name "$PG_SERVER_NAME" \
        --public-access Enabled

    echo "✅ Public access enabled."
fi

# Add firewall rule for the current machine's IP
echo ""
echo "🔥 Adding firewall rule for current IP ($PUBLIC_IP)..."
az postgres flexible-server firewall-rule create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$PG_SERVER_NAME" \
    --rule-name "AllowImportScriptAccess" \
    --start-ip-address "$PUBLIC_IP" \
    --end-ip-address "$PUBLIC_IP"
FIREWALL_RULE_ADDED=true
echo "✅ Firewall rule added."

if [[ "$IS_WAF" == "true" ]]; then
    echo ""
    echo "⏳ Waiting 5 minutes for WAF network changes to propagate..."
    sleep 300
    echo "✅ Propagation wait complete."
else
    echo ""
    echo "⏳ Waiting 30 seconds for firewall rule to propagate..."
    sleep 30
    echo "✅ Propagation wait complete."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Install required Azure CLI extensions
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📦 Ensuring Azure CLI extensions are up to date..."
az extension add --name rdbms-connect --upgrade --yes 2>/dev/null || true

# ──────────────────────────────────────────────────────────────────────────────
# Add current user as PostgreSQL Entra ID administrator
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "🔑 Adding current user as PostgreSQL Entra ID administrator..."
echo "   User: $USER_DISPLAY_NAME (Object ID: $USER_OBJECT_ID)"

TENANT_ID=$(az account show --query "tenantId" -o tsv)

RESULT=$(az rest --method PUT \
    --uri "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.DBforPostgreSQL/flexibleServers/${PG_SERVER_NAME}/administrators/${USER_OBJECT_ID}?api-version=2022-12-01" \
    --body "{\"properties\": {\"principalType\": \"$USER_PRINCIPAL_TYPE\", \"principalName\": \"$SIGNED_IN_USER_NAME\", \"tenantId\": \"$TENANT_ID\"}}" \
    2>&1) && echo "   Admin creation result: OK" || echo "   Admin creation response: $RESULT"

echo "   Listing current PostgreSQL administrators..."
az rest --method GET \
    --uri "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.DBforPostgreSQL/flexibleServers/${PG_SERVER_NAME}/administrators?api-version=2022-12-01" \
    --query "value[].{name:properties.principalName, type:properties.principalType}" \
    -o table 2>/dev/null || true

echo "✅ User configured as PostgreSQL administrator."

# ──────────────────────────────────────────────────────────────────────────────
# Wait for admin propagation
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "⏳ Waiting 120 seconds for admin changes to propagate..."
sleep 120
echo "✅ Propagation wait complete."

# ──────────────────────────────────────────────────────────────────────────────
# Install Python dependencies
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📦 Installing Python dependencies..."
pip install psycopg2-binary azure-identity --quiet

# ──────────────────────────────────────────────────────────────────────────────
# Import data into PostgreSQL using the logged-in user identity
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "📥 Importing sample data into PostgreSQL..."

$PYTHON - "$PG_FQDN" "$SIGNED_IN_USER_NAME" "$CSV_FILE" <<'PYTHON_SCRIPT'
import sys
import os
import psycopg2
from azure.identity import DefaultAzureCredential

pg_host = sys.argv[1]
pg_user = sys.argv[2]
csv_file = sys.argv[3]
db_name = "postgres"
target_table = "vector_store"

print(f"  PostgreSQL Host : {pg_host}")
print(f"  User            : {pg_user}")
print(f"  Database        : {db_name}")
print(f"  Target Table    : {target_table}")
print(f"  CSV File        : {csv_file}")

# Acquire Azure AD token using the logged-in user's identity
print("  Acquiring Azure AD token via DefaultAzureCredential...")
credential = DefaultAzureCredential()
token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
print("  ✅ Successfully acquired Azure AD token.")

db_params = {
    "user": pg_user,
    "password": token,
    "host": pg_host,
    "port": "5432",
    "dbname": db_name,
    "sslmode": "require",
}

try:
    print("  Connecting to PostgreSQL database...")
    with psycopg2.connect(**db_params) as conn:
        print("  ✅ Connected to PostgreSQL.")
        with conn.cursor() as cur:
            # Check if the target table exists
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);",
                (target_table,),
            )
            table_exists = cur.fetchone()[0]
            print(f"  Table '{target_table}' exists: {table_exists}")

            if not table_exists:
                print(f"  ⚠️  Table '{target_table}' does not exist. Skipping data import.")
                print("  💡 Hint: Run the table creation script first:")
                print("     scripts/run_create_table_script.sh")
                sys.exit(1)

            # Check current row count
            cur.execute(f"SELECT COUNT(*) FROM {target_table};")
            existing_count = cur.fetchone()[0]
            print(f"  Current row count in '{target_table}': {existing_count}")

            # Import CSV data
            with open(csv_file, "r", encoding="utf-8") as f:
                next(f)  # Skip header row
                cur.copy_expert(f"COPY {target_table} FROM STDIN WITH CSV", f)
            conn.commit()

            # Verify import
            cur.execute(f"SELECT COUNT(*) FROM {target_table};")
            new_count = cur.fetchone()[0]
            imported = new_count - existing_count
            print(f" Imported {imported} rows into '{target_table}' (total: {new_count}).")

except FileNotFoundError:
    print(f"  ⚠️  CSV file '{csv_file}' not found. Skipping data import.")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ Error during import: {e}")
    raise

print("  ✅ Data import completed successfully.")
PYTHON_SCRIPT

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Import Sample Data (PostgreSQL) — Complete"
echo "═══════════════════════════════════════════════════════════════"
echo "  Resource Group   : $RESOURCE_GROUP_NAME"
echo "  PostgreSQL Server : $PG_SERVER_NAME ($PG_FQDN)"
echo "  WAF Deployment   : $IS_WAF"
echo "  User             : $USER_DISPLAY_NAME ($SIGNED_IN_USER_NAME)"
echo "═══════════════════════════════════════════════════════════════"
