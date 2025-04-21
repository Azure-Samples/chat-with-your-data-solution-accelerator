#!/bin/bash

# This script sets up the environment variables for Azure OpenAI and runs the Docker Compose environment
# It sources values from the .env file but allows overriding them with command-line arguments

# Default path to .env file
ENV_FILE="./.env"

# Function to display usage information
function show_usage {
  echo "Usage: $0 [OPTIONS]"
  echo "Options:"
  echo "  -e, --env-file FILE  Path to .env file (default: ./.env)"
  echo "  -h, --help           Display this help message and exit"
}

# Parse command-line options
while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
  esac
done

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: Environment file '$ENV_FILE' not found."
  echo "Please create this file with your Azure OpenAI API credentials."
  exit 1
fi

# Load environment variables from .env file more safely
echo "Loading environment variables from $ENV_FILE"

# Use a temporary file for cleaned environment variables
TEMP_ENV_FILE=$(mktemp)
grep -v '^#' "$ENV_FILE" | grep -v '^$' | sed 's/=\s*/=/g' > "$TEMP_ENV_FILE"

# Read the file line by line to avoid issues with special characters
while IFS='=' read -r key value; do
  # Remove any trailing whitespace from key and value
  key=$(echo "$key" | xargs)

  # Skip if key contains invalid characters
  if [[ ! "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Warning: Skipping invalid environment variable: $key"
    continue
  fi

  # Export the variable
  export "$key=$value"
done < "$TEMP_ENV_FILE"

# Clean up
rm "$TEMP_ENV_FILE"

# Check if AZURE_OPENAI_ENDPOINT is set directly, if not, construct it from AZURE_OPENAI_RESOURCE
if [ -z "$AZURE_OPENAI_ENDPOINT" ] && [ -n "$AZURE_OPENAI_RESOURCE" ]; then
  export AZURE_OPENAI_ENDPOINT="https://${AZURE_OPENAI_RESOURCE}.openai.azure.com"
  echo "Constructed Azure OpenAI endpoint from resource name: $AZURE_OPENAI_ENDPOINT"
fi

# Verify essential variables are set
if [ -z "$AZURE_OPENAI_ENDPOINT" ] || [ -z "$AZURE_OPENAI_API_KEY" ]; then
  echo "Error: Azure OpenAI API credentials not found in $ENV_FILE"
  echo "Please ensure AZURE_OPENAI_ENDPOINT (or AZURE_OPENAI_RESOURCE) and AZURE_OPENAI_API_KEY are set."
  exit 1
fi

echo "Using Azure OpenAI endpoint: $AZURE_OPENAI_ENDPOINT"
echo "Using Azure OpenAI model: $AZURE_OPENAI_MODEL"
echo "API version: $AZURE_OPENAI_API_VERSION"

# Run Docker Compose with environment variables from .env
echo "Starting Docker Compose environment..."
docker-compose -f docker-compose.local.yml down --remove-orphans
docker-compose -f docker-compose.local.yml up --build

# Note: The environment variables will be passed to Docker Compose
# and then to the containers via ${VAR_NAME} syntax in docker-compose.local.yml
