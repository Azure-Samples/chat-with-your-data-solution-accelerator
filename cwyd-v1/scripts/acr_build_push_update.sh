#!/usr/bin/env bash
#
# Builds the application container images, pushes them to the per-deployment ACR,
# and updates the App Services / Function App.
#
# Usage:
#   ./scripts/acr_build_push_update.sh <resource-group> [--mode local|remote] [--tag TAG]
#
# Examples:
#   ./scripts/acr_build_push_update.sh "rg-cwyd-dev"
#   ./scripts/acr_build_push_update.sh "rg-cwyd-dev" --mode local --tag v1.0.0
#

set -euo pipefail
export MSYS_NO_PATHCONV=1

RESOURCE_GROUP=""
BUILD_MODE="remote"
IMAGE_TAG="latest"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            BUILD_MODE="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$RESOURCE_GROUP" ]]; then
                RESOURCE_GROUP="$1"
            else
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$RESOURCE_GROUP" ]]; then
    read -rp "Enter the resource group name: " RESOURCE_GROUP
    if [[ -z "$RESOURCE_GROUP" ]]; then
        echo "ERROR: Resource group name is required." >&2
        exit 1
    fi
fi

if [[ "$BUILD_MODE" != "remote" && "$BUILD_MODE" != "local" ]]; then
    echo "ERROR: --mode must be 'remote' or 'local'. Got: '$BUILD_MODE'" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"

# -------------------------------------------------------
# Load environment variables from .azure/<env>/.env
# -------------------------------------------------------
if [[ -d "${REPO_ROOT}/.azure" ]]; then
    while IFS= read -r line; do
        if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*# && "$line" =~ = ]]; then
            key="${line%%=*}"
            value="${line#*=}"
            value="${value%\"}"
            value="${value#\"}"
            case "$key" in
                ACR_NAME) ACR_NAME="$value" ;;
                ACR_LOGIN_SERVER) ACR_LOGIN_SERVER="$value" ;;
                SERVICE_WEB_RESOURCE_NAME) SERVICE_WEB_RESOURCE_NAME="$value" ;;
                SERVICE_ADMINWEB_RESOURCE_NAME) SERVICE_ADMINWEB_RESOURCE_NAME="$value" ;;
                SERVICE_FUNCTION_RESOURCE_NAME) SERVICE_FUNCTION_RESOURCE_NAME="$value" ;;
                AZURE_RESOURCE_GROUP) AZURE_RESOURCE_GROUP="$value" ;;
            esac
        fi
    done < <(find "${REPO_ROOT}/.azure" -name '.env' -type f 2>/dev/null | head -1 | xargs cat 2>/dev/null || true)
fi

echo ""
echo "=============================================="
echo " Build, Push & Update Images"
echo " Resource Group : ${RESOURCE_GROUP}"
echo " Mode           : ${BUILD_MODE}"
echo " Image Tag      : ${IMAGE_TAG}"
echo " Repo Root      : ${REPO_ROOT}"
echo "=============================================="
echo ""

# -------------------------------------------------------
# Discover shared resources
# -------------------------------------------------------
echo "Discovering resources in resource group '${RESOURCE_GROUP}'..."

if [[ -z "${ACR_NAME:-}" ]]; then
    ACR_NAME=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" --output tsv 2>/dev/null || true)
fi

if [[ -z "${ACR_NAME:-}" ]]; then
    echo "ERROR: No Azure Container Registry found in resource group '${RESOURCE_GROUP}'."
    exit 1
fi

if [[ -z "${ACR_LOGIN_SERVER:-}" ]]; then
    ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
fi

MI_CLIENT_ID=$(az identity list --resource-group "$RESOURCE_GROUP" --query "[0].clientId" --output tsv 2>/dev/null || true)

if [[ -z "${MI_CLIENT_ID:-}" ]]; then
    echo "ERROR: No user-assigned managed identity found in resource group '${RESOURCE_GROUP}'."
    exit 1
fi

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

echo "  ACR             : $ACR_LOGIN_SERVER"
echo "  Managed identity: $MI_CLIENT_ID"
echo ""

# -------------------------------------------------------
# Helper: get deployment outputs from Bicep
# -------------------------------------------------------
get_deployment_output() {
    local output_name="$1"
    local resource_group="$2"

    local deployment_name
    deployment_name=$(az deployment group list --resource-group "$resource_group" --query "[0].name" --output tsv 2>/dev/null || true)

    if [[ -z "${deployment_name:-}" ]]; then
        return
    fi

    az deployment group show \
        --name "$deployment_name" \
        --resource-group "$resource_group" \
        --query "properties.outputs.${output_name}.value" \
        --output tsv 2>/dev/null || true
}

# -------------------------------------------------------
# Helper: update a web app
# -------------------------------------------------------
update_web_app() {
    local app_name="$1"
    local image_name="$2"

    local full_image="${ACR_LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"
    echo "  Updating App Service: $app_name"
    echo "    Image: $full_image"

    # Set container image
    az webapp config container set \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$full_image" \
        --output none

    # Set DOCKER_REGISTRY_SERVER_URL app setting
    az webapp config appsettings set \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --settings "DOCKER_REGISTRY_SERVER_URL=https://${ACR_LOGIN_SERVER}" \
        --output none

    # Enable ACR pull with user-assigned managed identity
    local resource_id="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${app_name}"
    az resource update \
        --ids "$resource_id" \
        --set "properties.siteConfig.acrUseManagedIdentityCreds=true" \
        --set "properties.siteConfig.acrUserManagedIdentityID=$MI_CLIENT_ID" \
        --output none

    # Restart to apply changes
    az webapp restart \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP"
}

# -------------------------------------------------------
# Helper: update a function app
# -------------------------------------------------------
update_function_app() {
    local app_name="$1"
    local image_name="$2"

    local full_image="${ACR_LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"
    echo "  Updating Function App: $app_name"
    echo "    Image: $full_image"

    # Update Function App with container configuration using resource update
    # This sets linuxFxVersion=DOCKER|<image> and enables managed identity pull
    local resource_id="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${app_name}"
    az resource update \
        --ids "$resource_id" \
        --set "properties.siteConfig.linuxFxVersion=DOCKER|${full_image}" \
        --set "properties.siteConfig.acrUseManagedIdentityCreds=true" \
        --set "properties.siteConfig.acrUserManagedIdentityID=$MI_CLIENT_ID" \
        --output none

    # Restart to apply changes
    az functionapp restart \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP"
}

# -------------------------------------------------------
# Build and push images
# -------------------------------------------------------
IMAGE_DEFINITIONS=(
    "docker/Frontend.Dockerfile:rag-webapp"
    "docker/Admin.Dockerfile:rag-adminwebapp"
    "docker/Backend.Dockerfile:rag-backend"
)

echo ""
if [[ "$BUILD_MODE" == "local" ]]; then
    echo "--- LOCAL BUILD (Docker daemon) ---"

    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed or not in PATH."
        echo "Install Docker Desktop or use '--mode remote' instead."
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."
        exit 1
    fi

    echo "Logging in to ACR '$ACR_NAME'..."
    az acr login --name "$ACR_NAME"

    for dockerfile in "${IMAGE_DEFINITIONS[@]}"; do
        dockerfile_path="${dockerfile%%:*}"
        image_name="${dockerfile##*:}"
        full_tag="${ACR_LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"

        echo ""
        echo "[$image_name] Building from $dockerfile_path ..."
        docker build --file "$REPO_ROOT/$dockerfile_path" --tag "$full_tag" "$REPO_ROOT"

        echo "[$image_name] Pushing $full_tag ..."
        docker push "$full_tag"

        echo "[$image_name] OK"
    done
else
    echo "--- REMOTE BUILD (ACR Tasks) ---"
    echo "    Note: your Azure identity needs Contributor or AcrPush access on the ACR."
    echo ""

    for dockerfile in "${IMAGE_DEFINITIONS[@]}"; do
        dockerfile_path="${dockerfile%%:*}"
        image_name="${dockerfile##*:}"
        full_tag="${image_name}:${IMAGE_TAG}"

        echo "[$image_name] Submitting remote build to ACR '$ACR_NAME' ..."
        az acr build \
            --registry "$ACR_NAME" \
            --image "$full_tag" \
            --file "$dockerfile_path" \
            "$REPO_ROOT"

        echo "[$image_name] OK"
    done
fi

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
echo ""
echo "=============================================="
echo " Build & Push Complete"
echo "=============================================="
echo " Images pushed to ${ACR_LOGIN_SERVER}:"
echo "   ${ACR_LOGIN_SERVER}/rag-webapp:${IMAGE_TAG}"
echo "   ${ACR_LOGIN_SERVER}/rag-adminwebapp:${IMAGE_TAG}"
echo "   ${ACR_LOGIN_SERVER}/rag-backend:${IMAGE_TAG}"

# -------------------------------------------------------
# Discover and update each service
# -------------------------------------------------------
echo ""
echo "Updating web App Services..."

# -- Web app --
APP_NAME="${SERVICE_WEB_RESOURCE_NAME:-}"
if [[ -z "$APP_NAME" ]]; then
    APP_LIST=$(az webapp list --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null || true)
    if [[ -n "$APP_LIST" ]]; then
        # Try tag first
        APP_NAME=$(echo "$APP_LIST" | jq -r '.[] | select(.tags and .tags."azd-service-name" == "web-docker") | .name' | head -1 || true)

        # Fallback: try name pattern - no "admin" in name for web apps
        if [[ -z "$APP_NAME" ]]; then
            APP_NAME=$(echo "$APP_LIST" | jq -r '.[] | select(.name | test("admin") | not) | .name' | head -1 || true)
        fi

        # Fallback: try deployment outputs from Bicep
        if [[ -z "$APP_NAME" ]]; then
            APP_NAME=$(get_deployment_output "SERVICE_WEB_RESOURCE_NAME" "$RESOURCE_GROUP" || true)
        fi
    fi
fi

if [[ -n "$APP_NAME" ]]; then
    update_web_app "$APP_NAME" "rag-webapp"
else
    echo "  WARNING: No App Service found for web app - skipping."
fi

# -- Admin web app --
ADMIN_APP_NAME="${SERVICE_ADMINWEB_RESOURCE_NAME:-}"
if [[ -z "$ADMIN_APP_NAME" ]]; then
    APP_LIST=$(az webapp list --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null || true)
    if [[ -n "$APP_LIST" ]]; then
        # Try tag first
        ADMIN_APP_NAME=$(echo "$APP_LIST" | jq -r '.[] | select(.tags and .tags."azd-service-name" == "adminweb-docker") | .name' | head -1 || true)

        # Fallback: try name pattern - "admin" must be in name for admin apps
        if [[ -z "$ADMIN_APP_NAME" ]]; then
            ADMIN_APP_NAME=$(echo "$APP_LIST" | jq -r '.[] | select(.name | test("admin")) | .name' | head -1 || true)
        fi

        # Fallback: try deployment outputs from Bicep
        if [[ -z "$ADMIN_APP_NAME" ]]; then
            ADMIN_APP_NAME=$(get_deployment_output "SERVICE_ADMINWEB_RESOURCE_NAME" "$RESOURCE_GROUP" || true)
        fi
    fi
fi

if [[ -n "$ADMIN_APP_NAME" ]]; then
    update_web_app "$ADMIN_APP_NAME" "rag-adminwebapp"
else
    echo "  WARNING: No App Service found for admin app - skipping."
fi

# -- Function App --
echo ""
echo "Updating Function App..."
FUNC_APP_NAME="${SERVICE_FUNCTION_RESOURCE_NAME:-}"

if [[ -z "$FUNC_APP_NAME" ]]; then
    FUNC_LIST=$(az functionapp list --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null || true)
    if [[ -n "$FUNC_LIST" ]]; then
        # Try tag first
        FUNC_APP_NAME=$(echo "$FUNC_LIST" | jq -r '.[] | select(.tags and .tags."azd-service-name" == "function-docker") | .name' | head -1 || true)

        # Fallback: use first available
        if [[ -z "$FUNC_APP_NAME" ]]; then
            FUNC_APP_NAME=$(echo "$FUNC_LIST" | jq -r '.[0].name' 2>/dev/null || true)
        fi

        # Fallback: try deployment outputs from Bicep
        if [[ -z "$FUNC_APP_NAME" ]]; then
            FUNC_APP_NAME=$(get_deployment_output "SERVICE_FUNCTION_RESOURCE_NAME" "$RESOURCE_GROUP" || true)
        fi
    fi
fi

if [[ -n "$FUNC_APP_NAME" ]]; then
    update_function_app "$FUNC_APP_NAME" "rag-backend"
else
    echo "  WARNING: No Function App found in resource group '${RESOURCE_GROUP}' - skipping."
fi

echo ""
echo "=============================================="
echo " ACR Build, Push & Update complete"
echo "=============================================="
