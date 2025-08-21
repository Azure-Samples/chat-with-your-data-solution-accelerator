#!/bin/bash

# Fixed script to disable Azure App Service authentication
# This script addresses the "Bad Request" error by setting app settings individually

set -e

# Configuration
RESOURCE_GROUP=""
FRONTEND_APP=""
ADMIN_APP=""
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to extract app names and resource group
extract_deployment_info() {
    log_info "Extracting deployment information..."

    # Try to get URLs from environment variables
    if [ -n "$FRONTEND_WEBSITE_URL" ]; then
        FRONTEND_APP=$(echo "$FRONTEND_WEBSITE_URL" | sed 's|https://||;s|\.azurewebsites\.net.*||')
        log_success "Frontend app: $FRONTEND_APP"
    fi

    if [ -n "$ADMIN_WEBSITE_URL" ]; then
        ADMIN_APP=$(echo "$ADMIN_WEBSITE_URL" | sed 's|https://||;s|\.azurewebsites\.net.*||')
        log_success "Admin app: $ADMIN_APP"
    fi

    # Find resource group
    if [ -n "$FRONTEND_APP" ]; then
        RESOURCE_GROUP=$(az webapp list --query "[?name=='$FRONTEND_APP'].resourceGroup" -o tsv | head -1)
        if [ -n "$RESOURCE_GROUP" ]; then
            log_success "Resource group: $RESOURCE_GROUP"
        fi
    fi

    if [ -z "$RESOURCE_GROUP" ]; then
        log_error "Could not determine resource group"
        exit 1
    fi

    log_info "Configuration:"
    log_info "  Resource Group: $RESOURCE_GROUP"
    log_info "  Frontend App: ${FRONTEND_APP:-'Not found'}"
    log_info "  Admin App: ${ADMIN_APP:-'Not found'}"
}

# Function to set a single app setting with retry logic
set_app_setting() {
    local app_name=$1
    local rg_name=$2
    local setting_name=$3
    local setting_value=$4
    local max_retries=3
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        log_info "Setting $setting_name=$setting_value for $app_name (attempt $((retry_count + 1)))"

        if az webapp config appsettings set \
            --name "$app_name" \
            --resource-group "$rg_name" \
            --settings "$setting_name=$setting_value" \
            --output none 2>/dev/null; then
            log_success "Successfully set $setting_name=$setting_value"
            return 0
        else
            retry_count=$((retry_count + 1))
            log_warning "Failed to set $setting_name, retrying in 5 seconds..."
            sleep 5
        fi
    done

    log_error "Failed to set $setting_name after $max_retries attempts"
    return 1
}

# Function to disable authentication and set app settings
disable_auth_and_set_settings() {
    local app_name=$1
    local rg_name=$2

    if [ -z "$app_name" ] || [ -z "$rg_name" ]; then
        log_warning "Skipping - missing app name or resource group"
        return
    fi

    log_info "=== Configuring $app_name ==="

    # Verify app exists
    if ! az webapp show --name "$app_name" --resource-group "$rg_name" --output none 2>/dev/null; then
        log_error "App $app_name not found in resource group $rg_name"
        return 1
    fi

    # Step 1: Disable authentication
    log_info "Disabling authentication..."
    if az webapp auth update \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --enabled false \
        --action AllowAnonymous \
        --output none 2>/dev/null; then
        log_success "Authentication disabled successfully"
    else
        log_warning "Failed to disable authentication, continuing..."
    fi

    # Step 2: Set app settings individually to avoid "Bad Request" error
    log_info "Setting authentication app settings individually..."

    # Critical settings that control authentication behavior
    declare -A auth_settings=(
        ["FORCE_NO_AUTH"]="true"
        ["ENFORCE_AUTH"]="false"
        ["AUTH_ENABLED"]="false"
        ["AZURE_USE_AUTHENTICATION"]="false"
        ["AZURE_ENABLE_AUTH"]="false"
        ["REQUIRE_AUTHENTICATION"]="false"
        ["AUTHENTICATION_ENABLED"]="false"
        ["WEBSITES_AUTH_ENABLED"]="false"
        ["WEBSITE_AUTH_ENABLED"]="false"
        ["AZURE_AUTH_ENABLED"]="false"
        ["ENABLE_AUTHENTICATION"]="false"
        ["DISABLE_AUTHENTICATION"]="true"
        ["NO_AUTH"]="true"
        ["SKIP_AUTH"]="true"
    )

    local failed_settings=0
    for setting_name in "${!auth_settings[@]}"; do
        if ! set_app_setting "$app_name" "$rg_name" "$setting_name" "${auth_settings[$setting_name]}"; then
            failed_settings=$((failed_settings + 1))
        fi
        # Small delay between settings to avoid rate limiting
        sleep 2
    done

    if [ $failed_settings -gt 0 ]; then
        log_warning "$failed_settings app settings failed to set"
    else
        log_success "All app settings configured successfully"
    fi

    # Step 3: Restart the app
    log_info "Restarting $app_name..."
    if az webapp restart --name "$app_name" --resource-group "$rg_name" --output none 2>/dev/null; then
        log_success "App restarted successfully"
    else
        log_warning "Failed to restart app"
    fi

    # Step 4: Verify critical settings
    log_info "Verifying critical settings for $app_name..."
    sleep 10  # Wait for settings to propagate

    FORCE_NO_AUTH_VALUE=$(az webapp config appsettings list \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --query "[?name=='FORCE_NO_AUTH'].value | [0]" \
        --output tsv 2>/dev/null || echo "")

    ENFORCE_AUTH_VALUE=$(az webapp config appsettings list \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --query "[?name=='ENFORCE_AUTH'].value | [0]" \
        --output tsv 2>/dev/null || echo "")

    if [ "$FORCE_NO_AUTH_VALUE" = "true" ]; then
        log_success "✓ FORCE_NO_AUTH is correctly set to: $FORCE_NO_AUTH_VALUE"
    else
        log_error "✗ FORCE_NO_AUTH is not set correctly: '$FORCE_NO_AUTH_VALUE'"
    fi

    if [ "$ENFORCE_AUTH_VALUE" = "false" ]; then
        log_success "✓ ENFORCE_AUTH is correctly set to: $ENFORCE_AUTH_VALUE"
    else
        log_error "✗ ENFORCE_AUTH is not set correctly: '$ENFORCE_AUTH_VALUE'"
    fi

    log_success "Configuration completed for $app_name"
}

# Function to test app accessibility
test_app_accessibility() {
    local app_url=$1
    local app_name=$2

    if [ -z "$app_url" ]; then
        log_warning "No URL provided for $app_name"
        return
    fi

    log_info "Testing accessibility for $app_name at $app_url"

    # Test with multiple attempts
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout 30 \
            --max-time 60 \
            --location \
            --user-agent "Mozilla/5.0 (compatible; AuthTest/1.0)" \
            "$app_url" 2>/dev/null || echo "000")

        case $HTTP_CODE in
            200)
                log_success "$app_name is accessible (HTTP $HTTP_CODE) - Authentication disabled successfully!"
                return 0
                ;;
            302|301)
                log_success "$app_name is accessible (HTTP $HTTP_CODE) - Redirecting but accessible"
                return 0
                ;;
            401)
                log_error "$app_name returned HTTP $HTTP_CODE - Authentication still required"
                ;;
            403)
                log_error "$app_name returned HTTP $HTTP_CODE - Access forbidden"
                ;;
            000)
                log_warning "$app_name is not responding (attempt $attempt/$max_attempts)"
                ;;
            *)
                log_warning "$app_name returned HTTP $HTTP_CODE (attempt $attempt/$max_attempts)"
                ;;
        esac

        if [ $attempt -lt $max_attempts ]; then
            log_info "Waiting 30 seconds before retry..."
            sleep 30
        fi
        attempt=$((attempt + 1))
    done
}

# Function to list all current app settings for debugging
debug_app_settings() {
    local app_name=$1
    local rg_name=$2

    log_info "=== Debug: Current app settings for $app_name ==="

    # List all authentication-related settings
    local auth_related_settings=$(az webapp config appsettings list \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --query "[?contains(name, 'AUTH') || contains(name, 'FORCE')].{name:name,value:value}" \
        --output table 2>/dev/null || echo "Failed to retrieve settings")

    echo "$auth_related_settings"
}

# Main execution
main() {
    log_info "Starting authentication disable process..."

    # Azure login check
    if ! az account show --output none 2>/dev/null; then
        log_error "Not logged into Azure CLI. Please run 'az login' first."
        exit 1
    fi

    # Show current subscription
    CURRENT_SUB=$(az account show --query "name" --output tsv)
    log_info "Using Azure subscription: $CURRENT_SUB"

    # Extract deployment information
    extract_deployment_info

    # Configure both apps
    if [ -n "$FRONTEND_APP" ]; then
        disable_auth_and_set_settings "$FRONTEND_APP" "$RESOURCE_GROUP"
        debug_app_settings "$FRONTEND_APP" "$RESOURCE_GROUP"
    else
        log_warning "Frontend app not found, skipping"
    fi

    if [ -n "$ADMIN_APP" ]; then
        disable_auth_and_set_settings "$ADMIN_APP" "$RESOURCE_GROUP"
        debug_app_settings "$ADMIN_APP" "$RESOURCE_GROUP"
    else
        log_warning "Admin app not found, skipping"
    fi

    # Wait for changes to propagate
    log_info "Waiting 2 minutes for changes to propagate..."
    sleep 120

    # Test accessibility
    log_info "=== Testing Application Accessibility ==="
    if [ -n "$FRONTEND_WEBSITE_URL" ]; then
        test_app_accessibility "$FRONTEND_WEBSITE_URL" "Frontend"
    fi

    if [ -n "$ADMIN_WEBSITE_URL" ]; then
        test_app_accessibility "$ADMIN_WEBSITE_URL" "Admin"
    fi

    log_success "Authentication disable process completed!"
    log_info "If you still see authentication errors, wait an additional 10-15 minutes for full propagation."
}

# Run the main function
main "$@"
