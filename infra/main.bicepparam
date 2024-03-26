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

// We need the resourceToken to be unique for each deployment (copied from the main.bicep)
var subscriptionId = readEnvironmentVariable('AZURE_SUBSCRIPTION_ID', 'subscription_id')
param resourceToken = toLower(uniqueString(subscriptionId, environmentName, location))

// Retrieve the Search Name from the Search Endpoint (if it exists)
var azureAISearcEndpoint = readEnvironmentVariable('AZURE_SEARCH_SERVICE', 'https://./')
var searchSerivceName = split(substring(azureAISearcEndpoint, 8, length(azureAISearcEndpoint) - 9), '.')[0]
param azureAISearchName = searchSerivceName == '' ? 'search-${resourceToken}' : searchSerivceName

param azureSearchIndex = readEnvironmentVariable('AZURE_SEARCH_INDEX', 'index-${resourceToken}')
param azureOpenAIResourceName = readEnvironmentVariable('AZURE_OPENAI_RESOURCE', 'openai-${resourceToken}')

