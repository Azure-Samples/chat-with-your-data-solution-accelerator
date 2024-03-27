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

// Retrieve the Search Name from the Search Endpoint which will be in the format 
// "https://uniquename.search.windows.net/" It will end in a slash. Bicep forces us to have a default, so we use
// a default that we can manipulate in the same way to reduce another condition.  
// length(azureAISearchEndpoint) - 9) cuts the https:// and the trailing slash. We then take the first "part" of
// the split which will be '' if there is no value set. If its null we assume the user is creating a new search
// service.
var azureAISearchEndpoint = readEnvironmentVariable('AZURE_SEARCH_SERVICE', 'https://./')
var searchServiceName = split(substring(azureAISearchEndpoint, 8, length(azureAISearchEndpoint) - 9), '.')[0]
param azureAISearchName = searchServiceName == '' ? 'search-${resourceToken}' : searchServiceName

param azureSearchIndex = readEnvironmentVariable('AZURE_SEARCH_INDEX', 'index-${resourceToken}')
param azureOpenAIResourceName = readEnvironmentVariable('AZURE_OPENAI_RESOURCE', 'openai-${resourceToken}')
