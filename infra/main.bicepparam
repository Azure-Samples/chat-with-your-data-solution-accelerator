using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'env_name')

param location = readEnvironmentVariable('AZURE_LOCATION', 'location')

param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', 'principal_id')

// Please make sure to set this value to false when using rbac with AZURE_AUTH_TYPE
param useKeyVault = bool(readEnvironmentVariable('USE_KEY_VAULT', 'true'))

param authType = readEnvironmentVariable('AZURE_AUTH_TYPE', 'keys')

param hostingModel = readEnvironmentVariable('AZURE_APP_SERVICE_HOSTING_MODEL', 'code')

// The following are being renamed to align with the new naming convention
// we manipulate existing resources here to maintain backwards compatibility
var azureAISearcEndpoint = readEnvironmentVariable('AZURE_SEARCH_SERVICE', 'https://./')
var endpointLength = length(azureAISearcEndpoint)
param azureAISearchName = split(substring(azureAISearcEndpoint, 8, endpointLength - 9), '.')[0]
param azureSearchIndex = readEnvironmentVariable('AZURE_SEARCH_INDEX', '')
param azureOpenAIResourceName = readEnvironmentVariable('AZURE_OPENAI_RESOURCE', '')
