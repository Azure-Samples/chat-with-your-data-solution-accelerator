#!/usr/bin/env bash
# shellcheck shell=bash
#
# SYNOPSIS
#   Builds the v2 container images, pushes them to ACR, and rolls out new
#   revisions to all three Container Apps (frontend, backend, function).
#
# DESCRIPTION
#   Uses ACR Tasks (remote build — no local Docker required) to build images
#   from docker/Dockerfile.*, then updates the deployed Container Apps.
#   Works for both plain and WAF (private networking) deployments: the ACR
#   is temporarily unlocked for the remote build and re-locked on exit.
#
# OPTIONS
#   -g, --resource-group  Azure resource group that contains the ACR and
#                         Container Apps (required)
#   -t, --tag             Image tag to push (default: latest)
#
# EXAMPLES
#   ./infra/scripts/post-provision/acr_build_push_update.sh -g rg-cwyd-dev
#   ./infra/scripts/post-provision/acr_build_push_update.sh -g rg-cwyd-dev -t v1.2.0

set -euo pipefail
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
# Prevent MSYS/Git Bash from mangling Windows paths passed to az.exe
export MSYS_NO_PATHCONV=1

# =============================================================================
# Argument parsing
# =============================================================================

RESOURCE_GROUP_NAME=""
TAG="latest"

usage() {
    echo "Usage: $0 -g <ResourceGroupName> [-t <Tag>]"
    echo "  -g, --resource-group  Azure resource group (required)"
    echo "  -t, --tag             Image tag (default: latest)"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -g|--resource-group) RESOURCE_GROUP_NAME="$2"; shift 2 ;;
        -t|--tag)            TAG="$2";                 shift 2 ;;
        -h|--help)           usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

if [[ -z "$RESOURCE_GROUP_NAME" ]]; then
    echo "Error: -g <ResourceGroupName> is required." >&2
    usage
fi

SCRIPT_START=$(date +%s)

# =============================================================================
# Service definitions — one entry per deployable service.
# Add a row here to onboard a new service; nothing else needs to change.
# =============================================================================
# Parallel arrays: Name, Dockerfile, ServiceTag
SVC_NAMES=(       "rag-frontend"              "rag-backend"              "rag-functions"             )
SVC_DOCKERFILES=( "docker/Dockerfile.frontend" "docker/Dockerfile.backend" "docker/Dockerfile.functions" )
SVC_TAGS=(        "frontend"                  "backend"                  "function"                  )

# Tracks whether THIS run temporarily opened a WAF-locked ACR (for cleanup)
ACR_OPENED_FOR_BUILD=false
ACR_NAME=""
ACR_LOGIN_SERVER=""

# =============================================================================
# Helpers — path conversion (Git Bash / MSYS on Windows)
# =============================================================================

# Convert a POSIX path to a Windows-native path when running under Git Bash or
# MSYS. az.exe is a Windows binary and, with MSYS_NO_PATHCONV=1, it receives
# raw POSIX paths that it cannot resolve. On Linux/macOS cygpath is absent, so
# the path is returned unchanged.
to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s' "$1"
    fi
}

# =============================================================================
# Helpers — print utilities (ANSI colours)
# =============================================================================

CY='\033[0;36m'   # Cyan
GR='\033[0;32m'   # Green
YL='\033[0;33m'   # Yellow
WH='\033[1;37m'   # White
DG='\033[0;90m'   # Dark gray
RS='\033[0m'      # Reset

write_step() {
    local number=$1 total=$2 title=$3
    echo ""
    echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RS}"
    echo -e "${CY}  Step ${number} / ${total}  |  ${title}${RS}"
    echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RS}"
}

write_success() { echo -e "${GR}  [OK]  $1${RS}"; }
write_info()    { echo -e "${WH}  >>   $1${RS}"; }
write_warn()    { echo -e "${YL}  [!]  $1${RS}"; }
write_elapsed() {
    local now elapsed mins secs
    now=$(date +%s)
    elapsed=$(( now - SCRIPT_START ))
    mins=$(( elapsed / 60 ))
    secs=$(( elapsed % 60 ))
    echo -e "${DG}  Elapsed: $(printf '%02d:%02d' $mins $secs)${RS}"
}

# =============================================================================
# Helpers — ACR public-access management (WAF deployments)
# =============================================================================

enable_acr_public_access() {
    local public_access
    public_access=$(az acr show -n "$ACR_NAME" --query publicNetworkAccess --output tsv 2>/dev/null || true)
    if [[ "$public_access" == "Disabled" ]]; then
        write_warn "ACR is WAF-locked — temporarily enabling public network access for build"
        az acr update -n "$ACR_NAME" --public-network-enabled true --default-action Allow \
            --output none --only-show-errors
        ACR_OPENED_FOR_BUILD=true
        write_warn "Waiting 45s for network rule propagation..."
        sleep 45
    else
        write_info "ACR public access: ${public_access:-unknown} (no WAF unlock needed)"
    fi
}

restore_acr_public_access() {
    if [[ "$ACR_OPENED_FOR_BUILD" == "true" ]]; then
        ACR_OPENED_FOR_BUILD=false
        write_warn "Re-locking ACR (disabling public network access)"
        if az acr update -n "$ACR_NAME" --public-network-enabled false --default-action Deny \
                --output none --only-show-errors; then
            write_success "ACR re-locked"
        else
            write_warn "Failed to re-lock. Run manually: az acr update -n $ACR_NAME --public-network-enabled false --default-action Deny"
        fi
    fi
}

# Ensure ACR is re-locked on any exit (success or failure)
trap restore_acr_public_access EXIT

# =============================================================================
# Helper — roll out a new revision to a Container App
# =============================================================================

update_container_app() {
    local app_name=$1 image_name=$2
    local full_image="${ACR_LOGIN_SERVER}/${image_name}:${TAG}"
    local rev_suffix
    rev_suffix=$(date -u +%Y%m%d%H%M%S)

    write_info "Deploying  : $app_name"
    write_info "  Image    : $full_image"
    write_info "  Suffix   : $rev_suffix"

    az containerapp update \
        --name            "$app_name" \
        --resource-group  "$RESOURCE_GROUP_NAME" \
        --image           "$full_image" \
        --revision-suffix "$rev_suffix" \
        --output none
    write_success "$app_name updated"
}

# =============================================================================
# Banner
# =============================================================================

TOTAL_STEPS=4
SVC_LIST="${SVC_NAMES[*]}"
SVC_LIST="${SVC_LIST// /, }"

echo ""
echo -e "${CY}  CWYD v2  |  Build - Push - Deploy${RS}"
echo -e "${CY}  Resource Group : $RESOURCE_GROUP_NAME${RS}"
echo -e "${CY}  Image Tag      : $TAG${RS}"
echo -e "${CY}  Services       : $SVC_LIST${RS}"

# =============================================================================
# Step 1 - Discover resources
# =============================================================================
write_step 1 "$TOTAL_STEPS" "Discover ACR and Container Apps"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
write_info "Repo root : $REPO_ROOT"

ACR_NAME=$(az acr list --resource-group "$RESOURCE_GROUP_NAME" --query "[0].name" --output tsv 2>/dev/null || true)
if [[ -z "$ACR_NAME" ]]; then
    echo "Error: No ACR found in '$RESOURCE_GROUP_NAME'. Run 'azd provision' first." >&2
    exit 1
fi
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
write_success "ACR : $ACR_LOGIN_SERVER"

MI_CLIENT_ID=$(az identity list --resource-group "$RESOURCE_GROUP_NAME" --query "[0].clientId" --output tsv 2>/dev/null || true)
if [[ -z "$MI_CLIENT_ID" ]]; then
    write_warn "No UAMI found — image pulls may fail if Bicep UAMI wiring is missing"
else
    write_success "UAMI client id : $MI_CLIENT_ID"
fi
write_elapsed

# =============================================================================
# Step 2 - Remote ACR build (one image at a time)
# =============================================================================
write_step 2 "$TOTAL_STEPS" "Remote Build via ACR Tasks (no local Docker needed)"
write_info "Your Azure identity needs 'AcrPush' or 'Contributor' on the ACR."

BUILD_COUNT=0
TOTAL_BUILDS=${#SVC_NAMES[@]}

enable_acr_public_access

for i in "${!SVC_NAMES[@]}"; do
    SVC_NAME="${SVC_NAMES[$i]}"
    SVC_DOCKERFILE="${SVC_DOCKERFILES[$i]}"

    BUILD_COUNT=$(( BUILD_COUNT + 1 ))
    echo ""
    echo -e "${WH}  [$BUILD_COUNT/$TOTAL_BUILDS] $SVC_NAME${RS}"
    write_info "  Dockerfile : $SVC_DOCKERFILE"
    write_info "  Target tag : $ACR_LOGIN_SERVER/$SVC_NAME:$TAG"

    CONTEXT_DIR="$(mktemp -d "/tmp/acr-ctx-${SVC_NAME}-XXXX")"
    write_info "  Copying build context to $CONTEXT_DIR..."

    cp -r "$REPO_ROOT/src"            "$CONTEXT_DIR/"
    cp -r "$REPO_ROOT/docker"         "$CONTEXT_DIR/"
    cp    "$REPO_ROOT/pyproject.toml" "$CONTEXT_DIR/"
    cp    "$REPO_ROOT/uv.lock"        "$CONTEXT_DIR/"

    write_info "  Submitting to ACR Tasks — streaming build log..."
    build_exit=0
    az acr build \
        --registry "$ACR_NAME" \
        --image    "${SVC_NAME}:${TAG}" \
        --file     "$(to_native_path "${CONTEXT_DIR}/${SVC_DOCKERFILE}")" \
        "$(to_native_path "$CONTEXT_DIR")" || build_exit=$?

    rm -rf "$CONTEXT_DIR"

    if [[ $build_exit -ne 0 ]]; then
        echo "Error: Build failed for $SVC_NAME. See ACR Task log above." >&2
        exit 1
    fi
    write_success "${SVC_NAME}:${TAG} pushed"
done

write_elapsed

# =============================================================================
# Step 3 - Deploy new revisions to Container Apps
# =============================================================================
write_step 3 "$TOTAL_STEPS" "Deploy New Revisions to Container Apps"

CA_COUNT=$(az containerapp list --resource-group "$RESOURCE_GROUP_NAME" --query "length(@)" --output tsv 2>/dev/null || echo "0")
write_info "Found $CA_COUNT Container App(s) in '$RESOURCE_GROUP_NAME'"

for i in "${!SVC_NAMES[@]}"; do
    SVC_NAME="${SVC_NAMES[$i]}"
    SVC_SERVICE_TAG="${SVC_TAGS[$i]}"

    echo ""
    # Primary: azd-service-name tag set by azd provision
    APP_NAME=$(az containerapp list \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --query "[?tags.\"azd-service-name\"=='${SVC_SERVICE_TAG}'].name | [0]" \
        --output tsv 2>/dev/null || true)

    # Fallback: Bicep naming convention ca-<service>-<suffix>
    if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
        APP_NAME=$(az containerapp list \
            --resource-group "$RESOURCE_GROUP_NAME" \
            --query "[?starts_with(name, 'ca-${SVC_SERVICE_TAG}-')].name | [0]" \
            --output tsv 2>/dev/null || true)
    fi

    if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
        write_warn "No Container App found for service tag '${SVC_SERVICE_TAG}' — skipping"
        continue
    fi

    update_container_app "$APP_NAME" "$SVC_NAME"
done

write_elapsed

# =============================================================================
# Step 4 - Summary
# =============================================================================
write_step 4 "$TOTAL_STEPS" "Done"

NOW=$(date +%s)
ELAPSED=$(( NOW - SCRIPT_START ))
MINS=$(( ELAPSED / 60 ))
SECS=$(( ELAPSED % 60 ))

echo ""
echo -e "${GR}  Images deployed to $ACR_LOGIN_SERVER :${RS}"
for SVC_NAME in "${SVC_NAMES[@]}"; do
    echo -e "${GR}    $ACR_LOGIN_SERVER/$SVC_NAME:$TAG${RS}"
done
echo ""
write_success "Completed in $(printf '%02d:%02d' $MINS $SECS)"
