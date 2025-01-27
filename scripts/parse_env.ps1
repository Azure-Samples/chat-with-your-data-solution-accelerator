# Fetch the environment name from azd
$envName = azd env get-values --output json | ConvertFrom-Json | Select-Object -ExpandProperty AZURE_ENV_NAME

# Locate the .env file
$envFile = "$PWD/.azure/$envName/.env"

if (!(Test-Path $envFile)) {
    Write-Error "The .env file could not be found at: $envFile"
    exit 1
}

Write-Host "Reading the .env file at: $envFile"

# Function to parse and flatten JSON into specific key-value pairs
function Flatten-Json {
    param (
        [string]$prefix,
        [PSObject]$jsonObject
    )
    $flattened = @{}
    foreach ($property in $jsonObject.PSObject.Properties) {
        # Use prefix to create the full key name
        $key = "$prefix$($property.Name.ToUpper())"
        $value = $property.Value
        $flattened[$key] = $value
    }
    return $flattened
}

$output = @{}

foreach ($line in Get-Content -Path $envFile) {
    Write-Host "Processing line: $line"
    $key, $value = $line -split "=", 2

    # Check for specific JSON objects to flatten
    if ($key -in @("AZURE_OPENAI_MODEL_INFO", "AZURE_OPENAI_CONFIGURATION_INFO", "AZURE_OPENAI_EMBEDDING_MODEL_INFO", "AZURE_BLOB_STORAGE_INFO", "AZURE_FORM_RECOGNIZER_INFO", "AZURE_COSMOSDB_INFO", "AZURE_POSTGRESQL_INFO", "AZURE_SPEECH_SERVICE_INFO", "AZURE_SEARCH_SERVICE_INFO", "AZURE_COMPUTER_VISION_INFO", "AZURE_CONTENT_SAFETY_INFO", "AZURE_KEY_VAULT_INFO")) {
        # Try converting the string to JSON and flattening it
        try {
            # Remove the escaped quotes
            $unescapedValue = $value -replace '\\\"', '"'
            # Trim any unnecessary quotes around the value
            $cleanedValue = $unescapedValue.Trim('"')
            # Convert the cleaned JSON string into an object
            $jsonObject = $cleanedValue | ConvertFrom-Json

            # Determine the prefix based on the key
            $prefix = switch ($key) {
                "AZURE_OPENAI_MODEL_INFO" { "AZURE_OPENAI_" }
                "AZURE_OPENAI_CONFIGURATION_INFO" { "AZURE_OPENAI_" }
                "AZURE_OPENAI_EMBEDDING_MODEL_INFO" {"AZURE_OPENAI_EMBEDDING_"}
                "AZURE_BLOB_STORAGE_INFO" { "AZURE_BLOB_" }
                "AZURE_FORM_RECOGNIZER_INFO" {"AZURE_FORM_RECOGNIZER_"}
                "AZURE_COSMOSDB_INFO" { "AZURE_COSMOSDB_" }
                "AZURE_POSTGRESQL_INFO" {"AZURE_POSTGRESQL_"}
                "AZURE_SPEECH_SERVICE_INFO" {"AZURE_SPEECH_"}
                "AZURE_SEARCH_SERVICE_INFO" {"AZURE_SEARCH_"}
                "AZURE_COMPUTER_VISION_INFO" {"AZURE_COMPUTER_VISION_"}
                "AZURE_CONTENT_SAFETY_INFO" {"AZURE_CONTENT_SAFETY_"}
                "AZURE_KEY_VAULT_INFO" {"AZURE_KEY_VAULT_"}
            }

            # Flatten the JSON object
            $flattenedJson = Flatten-Json -prefix $prefix -jsonObject $jsonObject

            # Add each flattened key-value pair to the output
            foreach ($flattenedKey in $flattenedJson.Keys) {
                $output[$flattenedKey] = "`"$($flattenedJson[$flattenedKey])`""
            }
        } catch {
            Write-Error "Failed to parse JSON for key: $key, value: $value"
        }
    } else {
        # Keep non-JSON key-value pairs as-is
        $output[$key] = $value
    }
}

# Convert the hashtable to an array of strings in the format KEY=VALUE, sorted by key name
$output = $output.GetEnumerator() |
    Sort-Object -Property Key |
    ForEach-Object { "$($_.Key)=$($_.Value)" }

# Write the processed content back to the .env file
$output | Set-Content -Path $envFile -Force
Write-Host "Flattened .env file written back to: $envFile"
