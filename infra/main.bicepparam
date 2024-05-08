using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'env_name')

param location = readEnvironmentVariable('AZURE_LOCATION', 'location')

param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', 'principal_id')

// Please make sure to set this value to false when using rbac with AZURE_AUTH_TYPE
param useKeyVault = bool(readEnvironmentVariable('USE_KEY_VAULT', 'true'))

param authType = readEnvironmentVariable('AZURE_AUTH_TYPE', 'keys')

param hostingModel = readEnvironmentVariable('AZURE_APP_SERVICE_HOSTING_MODEL', 'code')

param azureOpenAIModel = readEnvironmentVariable('AZURE_OPENAI_MODEL', 'gpt-35-turbo-16k')
param azureOpenAIModelName = readEnvironmentVariable('AZURE_OPENAI_MODEL_NAME', 'gpt-35-turbo-16k')
param azureOpenAIModelVersion = readEnvironmentVariable('AZURE_OPENAI_MODEL_VERSION', '0613')
param azureOpenAIModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_MODEL_CAPACITY', '30'))
param useAdvancedImageProcessing = bool(readEnvironmentVariable('USE_ADVANCED_IMAGE_PROCESSING', 'false'))
param azureOpenAIVisionModel = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL', 'gpt-4-vision')
param azureOpenAIVisionModelName = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_NAME', 'gpt-4')
param azureOpenAIVisionModelVersion = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_VERSION', 'vision-preview')
param azureOpenAIVisionModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_CAPACITY', '10'))
param azureOpenAIEmbeddingModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY', '30'))

param computerVisionLocation = readEnvironmentVariable('AZURE_COMPUTER_VISION_LOCATION', '')

param azureSearchUseIntegratedVectorization = bool(readEnvironmentVariable('AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION', 'false'))

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
