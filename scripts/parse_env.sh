#!/bin/bash

# Fetch the environment name from azd
envName=$(azd env get-values --output json | grep -o '"AZURE_ENV_NAME": *"[^"]*' | sed 's/"AZURE_ENV_NAME": *"//')

# Ensure jq is installed
which jq || { echo "jq is not installed"; exit 1; }

# Locate the .env file
envFile="$PWD/.azure/$envName/.env"

if [[ ! -f "$envFile" ]]; then
    echo "The .env file could not be found at: $envFile" >&2
    exit 1
fi

echo "Reading the .env file at: $envFile"

# Function to parse and flatten JSON into specific key-value pairs
flatten_json() {
    local prefix="$1"
    local json_object="$2"
    echo "$json_object" | jq -r "to_entries | .[] | \"${prefix}\(.key | ascii_upcase)=\(.value | @sh)\""
}

declare -A output

# Read the .env file line by line
while IFS= read -r line; do
    echo "Processing line: $line"

    # Split the line into key and value
    key=$(echo "$line" | cut -d'=' -f1)
    value=$(echo "$line" | cut -d'=' -f2-)

    # Check for specific JSON objects to flatten
    case "$key" in
        "AZURE_OPENAI_MODEL_INFO"|"AZURE_OPENAI_CONFIGURATION_INFO"|"AZURE_OPENAI_EMBEDDING_MODEL_INFO"|"AZURE_BLOB_STORAGE_INFO"|"AZURE_FORM_RECOGNIZER_INFO"|"AZURE_COSMOSDB_INFO"|"AZURE_POSTGRESQL_INFO"|"AZURE_SPEECH_SERVICE_INFO"|"AZURE_SEARCH_SERVICE_INFO"|"AZURE_COMPUTER_VISION_INFO"|"AZURE_CONTENT_SAFETY_INFO"|"AZURE_KEY_VAULT_INFO")
            # Attempt to parse and flatten JSON
            unescapedValue=$(echo "$value" | sed 's/\\"/"/g') # Remove escaped quotes
            cleanedValue=$(echo "$unescapedValue" | sed 's/^"//' | sed 's/"$//') # Trim surrounding quotes
            if json_object=$(echo "$cleanedValue" | jq . 2>/dev/null); then
                # Determine the prefix based on the key
                prefix=""
                case "$key" in
                    "AZURE_OPENAI_MODEL_INFO") prefix="AZURE_OPENAI_" ;;
                    "AZURE_OPENAI_CONFIGURATION_INFO") prefix="AZURE_OPENAI_" ;;
                    "AZURE_OPENAI_EMBEDDING_MODEL_INFO") prefix="AZURE_OPENAI_EMBEDDING_" ;;
                    "AZURE_BLOB_STORAGE_INFO") prefix="AZURE_BLOB_" ;;
                    "AZURE_FORM_RECOGNIZER_INFO") prefix="AZURE_FORM_RECOGNIZER_" ;;
                    "AZURE_COSMOSDB_INFO") prefix="AZURE_COSMOSDB_" ;;
                    "AZURE_POSTGRESQL_INFO") prefix="AZURE_POSTGRESQL_" ;;
                    "AZURE_SPEECH_SERVICE_INFO") prefix="AZURE_SPEECH_" ;;
                    "AZURE_SEARCH_SERVICE_INFO") prefix="AZURE_SEARCH_" ;;
                    "AZURE_COMPUTER_VISION_INFO") prefix="AZURE_COMPUTER_VISION_" ;;
                    "AZURE_CONTENT_SAFETY_INFO") prefix="AZURE_CONTENT_SAFETY_" ;;
                    "AZURE_KEY_VAULT_INFO") prefix="AZURE_KEY_VAULT_" ;;
                esac
                # Flatten the JSON object
                while IFS= read -r flattened_line; do
                    flattened_key=$(echo "$flattened_line" | cut -d'=' -f1)
                    flattened_value=$(echo "$flattened_line" | cut -d'=' -f2-)
                    output["$flattened_key"]="$flattened_value"
                done < <(flatten_json "$prefix" "$json_object")
            else
                echo "Failed to parse JSON for key: $key, value: $value"
            fi
            ;;
        *)
            # Keep non-JSON key-value pairs as-is
            output["$key"]="$value"
            ;;
    esac
done < "$envFile"

# Write the processed content back to the .env file, sorted by key
{
    for key in $(printf "%s\n" "${!output[@]}" | sort); do
        echo "$key=${output[$key]}"
    done
} > "$envFile"

echo "Flattened and sorted .env file written back to: $envFile"
