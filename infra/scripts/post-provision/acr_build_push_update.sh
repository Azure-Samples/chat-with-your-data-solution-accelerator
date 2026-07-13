#!/usr/bin/env bash
#
# acr_build_push_update.sh
# -----------------------------------------------------------------------------
# Builds the v2 application container images, pushes them to the per-deployment
# Azure Container Registry (ACR), and updates the deployed Container Apps:
#   - Container Apps : frontend, backend, function
#
# The function service is deployed as a Container App (not an App Service
# Function App), so all three services are updated through the same path.
#
# Images are built remotely with ACR Tasks (`az acr build`), so no local Docker
# daemon is required.
#
# Usage:
#   ./infra/scripts/post-provision/acr_build_push_update.sh <resource-group> [--tag TAG]
#
# Examples:
#   ./infra/scripts/post-provision/acr_build_push_update.sh "rg-cwyd-dev"
#   ./infra/scripts/post-provision/acr_build_push_update.sh "rg-cwyd-dev" --tag v1.0.0
# -----------------------------------------------------------------------------

set -euo pipefail
export MSYS_NO_PATHCONV=1

# =============================================================================
# Defaults & constants
# =============================================================================
RESOURCE_GROUP=""
IMAGE_TAG="latest"

# Tracks whether this script temporarily opened a locked-down (WAF) ACR so the
# EXIT trap knows whether it needs to re-lock it.
ACR_OPENED_FOR_BUILD=false

# Image map: "<dockerfile path>:<image name>".
# Matches the docker/ Dockerfiles at the repo root and the bicep-defined image
# names.
IMAGE_DEFINITIONS=(
    "docker/Dockerfile.frontend:rag-frontend"
    "docker/Dockerfile.backend:rag-backend"
    "docker/Dockerfile.functions:rag-functions"
)

# Service discovery map for the update phase: "<azd-service-name>:<image name>".
CONTAINER_APP_SERVICES=(
    "frontend:rag-frontend"
    "backend:rag-backend"
    "function:rag-functions"
)

# =============================================================================
# Helper functions
# =============================================================================

# ---- Path helpers ------------------------------------------------------------

# Convert a path to a native Windows path when running under MSYS/Git Bash/Cygwin
# (where `az.exe` expects C:\... rather than /c/...). On Linux/macOS `cygpath`
# does not exist, so the original POSIX path is returned unchanged.
to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s' "$1"
    fi
}

# ---- ACR public access (WAF auto-detect; try/finally pattern from CGSA) ------

# Temporarily enable public network access on the ACR when it is locked down
# (WAF mode) so the remote build can reach the registry.
enable_acr_public_access() {
    local public_access
    public_access=$(az acr show -n "$ACR_NAME" --query publicNetworkAccess --output tsv 2>/dev/null || true)
    if [[ "$public_access" == "Disabled" ]]; then
        echo "===== ACR public access is disabled (WAF mode) - temporarily enabling for build ====="
        az acr update -n "$ACR_NAME" --public-network-enabled true --default-action Allow --output none --only-show-errors
        ACR_OPENED_FOR_BUILD=true
        echo "Waiting 45s for network rule propagation..."
        sleep 45
    fi
}

# Re-lock the ACR if (and only if) this script opened it. Registered on the EXIT
# trap so the registry is restored on both success and failure.
restore_acr_public_access() {
    if [[ "$ACR_OPENED_FOR_BUILD" == "true" ]]; then
        echo "===== Re-locking ACR (disabling public network access) ====="
        az acr update -n "$ACR_NAME" --public-network-enabled false --default-action Deny --output none --only-show-errors || \
            echo "WARNING: Failed to re-disable ACR public access. Re-lock manually: az acr update -n $ACR_NAME --public-network-enabled false --default-action Deny"
    fi
}

# ---- Service updates ---------------------------------------------------------

# Update a Container App (v2 frontend + backend) to a new image. Bicep already
# wires the ACR registry with the UAMI, so only the image is set here.
update_container_app() {
    local app_name="$1"
    local image_name="$2"

    local full_image="${ACR_LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"
    local revision_suffix="$(date +%Y%m%d%H%M%S)"
    echo "  Updating Container App: $app_name"
    echo "    Image: $full_image"
    echo "    Revision suffix: $revision_suffix"

    az containerapp update \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --image "$full_image" \
        --revision-suffix "$revision_suffix" \
        --output none
}

# =============================================================================
# 1. Parse command line arguments
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
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

# =============================================================================
# 2. Resolve repo root
# =============================================================================
# Script lives at <repo>/infra/scripts/post-provision/, so walk up 3 levels for
# the repo root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." >/dev/null 2>&1 && pwd)"

# =============================================================================
# 3. Resource group is authoritative
# =============================================================================
echo ""
echo "=============================================="
echo " Build, Push & Update Images"
echo " Resource Group : ${RESOURCE_GROUP}"
echo " Image Tag      : ${IMAGE_TAG}"
echo " Repo Root      : ${REPO_ROOT}"
echo "=============================================="
echo ""

# =============================================================================
# 4. Discover shared resources (ACR, managed identity, subscription)
# =============================================================================
echo "Discovering resources in resource group '${RESOURCE_GROUP}'..."

if [[ -z "${ACR_NAME:-}" ]]; then
    ACR_NAME=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" --output tsv 2>/dev/null || true)
fi

if [[ -z "${ACR_NAME:-}" ]]; then
    echo "ERROR: No Azure Container Registry found in resource group '${RESOURCE_GROUP}'." >&2
    echo "Run 'azd provision' to create infrastructure first." >&2
    exit 1
fi

if [[ -z "${ACR_LOGIN_SERVER:-}" ]]; then
    ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
fi

MI_CLIENT_ID=$(az identity list --resource-group "$RESOURCE_GROUP" --query "[0].clientId" --output tsv 2>/dev/null || true)

if [[ -z "${MI_CLIENT_ID:-}" ]]; then
    echo "ERROR: No user-assigned managed identity found in resource group '${RESOURCE_GROUP}'." >&2
    exit 1
fi

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

echo "  ACR             : $ACR_LOGIN_SERVER"
echo "  Managed identity: $MI_CLIENT_ID"
echo ""

# =============================================================================
# 5. Build and push images (remote ACR Tasks build)
# =============================================================================
echo ""
echo "--- REMOTE BUILD (ACR Tasks - no local Docker required) ---"
echo "    Note: your Azure identity needs Contributor or AcrPush access on the ACR."
echo ""

# Ensure the ACR is re-locked on exit (success or failure), then open it if WAF.
trap restore_acr_public_access EXIT
enable_acr_public_access

for dockerfile in "${IMAGE_DEFINITIONS[@]}"; do
    dockerfile_path="${dockerfile%%:*}"
    image_name="${dockerfile##*:}"
    full_tag="${image_name}:${IMAGE_TAG}"

    # az.exe needs native paths for --file and the build context; convert when
    # running under Git Bash/MSYS (no-op on Linux/macOS).
    dockerfile_native="$(to_native_path "${REPO_ROOT}/${dockerfile_path}")"
    build_context_native="$(to_native_path "${REPO_ROOT}")"

    echo "[$image_name] Submitting remote build to ACR '$ACR_NAME' ..."
    az acr build \
        --registry "$ACR_NAME" \
        --image "$full_tag" \
        --file "$dockerfile_native" \
        "$build_context_native"

    echo "[$image_name] OK"
done

# =============================================================================
# 6. Build & push summary
# =============================================================================
echo ""
echo "=============================================="
echo " Build & Push Complete"
echo "=============================================="
echo " Images pushed to ${ACR_LOGIN_SERVER}:"
echo "   ${ACR_LOGIN_SERVER}/rag-frontend:${IMAGE_TAG}"
echo "   ${ACR_LOGIN_SERVER}/rag-backend:${IMAGE_TAG}"
echo "   ${ACR_LOGIN_SERVER}/rag-functions:${IMAGE_TAG}"

# =============================================================================
# 7. Discover and update Container Apps (frontend + backend + function)
# =============================================================================
echo ""
echo "Updating Container Apps..."

CA_LIST_JSON=$(az containerapp list --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null || true)

for pair in "${CONTAINER_APP_SERVICES[@]}"; do
    service_tag="${pair%%:*}"
    image_name="${pair##*:}"

    # Discover the app via az server-side JMESPath (no jq dependency).
    # Prefer the azd-service-name tag; fall back to the ca-<service>-<suffix> name pattern.
    APP_NAME=$(az containerapp list --resource-group "$RESOURCE_GROUP" \
        --query "[?tags.\"azd-service-name\"=='${service_tag}'].name | [0]" \
        --output tsv 2>/dev/null || true)

    if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
        APP_NAME=$(az containerapp list --resource-group "$RESOURCE_GROUP" \
            --query "[?starts_with(name, 'ca-${service_tag}-')].name | [0]" \
            --output tsv 2>/dev/null || true)
    fi

    if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
        echo "  WARNING: No Container App for azd-service-name='$service_tag' in RG '$RESOURCE_GROUP' - skipping."
        continue
    fi

    update_container_app "$APP_NAME" "$image_name"
done

echo ""
echo "=============================================="
echo " ACR Build, Push & Update complete"
echo "=============================================="
