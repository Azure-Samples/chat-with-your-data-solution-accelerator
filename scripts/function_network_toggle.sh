#!/bin/bash
set -euo pipefail

ACTION="${1:-}"
if [[ "$ACTION" != "enable" && "$ACTION" != "disable" ]]; then
  echo "Usage: $0 <enable|disable>"
  exit 1
fi

# This hook only applies to container hosting; code hosting remains unchanged.
HOSTING_MODEL="${AZURE_APP_SERVICE_HOSTING_MODEL:-}"
if [[ "$HOSTING_MODEL" != "container" ]]; then
  echo "Skipping Function App network toggle: hosting model is '$HOSTING_MODEL' (not container)."
  exit 0
fi

FUNCTION_APP_NAME="${SERVICE_FUNCTION_RESOURCE_NAME:-}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"

if [[ -z "$FUNCTION_APP_NAME" || -z "$RESOURCE_GROUP" ]]; then
  echo "Skipping Function App network toggle: missing SERVICE_FUNCTION_RESOURCE_NAME or AZURE_RESOURCE_GROUP."
  exit 0
fi

if ! az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Skipping Function App network toggle: Function App '$FUNCTION_APP_NAME' not found in '$RESOURCE_GROUP'."
  exit 0
fi

# Only toggle when private endpoint exists, which is the WAF/private-networking scenario for container hosting.
FUNCTION_APP_ID=$(az functionapp show \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "id" \
  -o tsv)

PRIVATE_ENDPOINT_COUNT=$(az network private-endpoint list \
  --resource-group "$RESOURCE_GROUP" \
  --query "length([?contains(privateLinkServiceConnections[].privateLinkServiceId, '${FUNCTION_APP_ID}')])" \
  -o tsv 2>/dev/null || echo "0")

if [[ -z "$PRIVATE_ENDPOINT_COUNT" || "$PRIVATE_ENDPOINT_COUNT" -eq 0 ]]; then
  echo "Skipping Function App network toggle: no private endpoint is configured on '$FUNCTION_APP_NAME'."
  exit 0
fi

CURRENT_PUBLIC_ACCESS=$(az functionapp show \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "publicNetworkAccess" \
  -o tsv)

if [[ "$ACTION" == "enable" ]]; then
  if [[ "$CURRENT_PUBLIC_ACCESS" == "Enabled" ]]; then
    echo "Function App public access already enabled; no change needed."
    exit 0
  fi

  echo "Temporarily enabling Function App public access for deployment."
  az functionapp update \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --set publicNetworkAccess=Enabled >/dev/null
  echo "Function App public access enabled."
  exit 0
fi

if [[ "$CURRENT_PUBLIC_ACCESS" == "Disabled" ]]; then
  echo "Function App public access already disabled; no change needed."
  exit 0
fi

echo "Restoring Function App to private-only access."
az functionapp update \
  --name "$FUNCTION_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set publicNetworkAccess=Disabled >/dev/null
echo "Function App public access disabled."
