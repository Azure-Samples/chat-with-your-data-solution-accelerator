using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'env_name')
param location = readEnvironmentVariable('AZURE_LOCATION', 'location')
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', 'principal_id')

// Please make sure to set this value to false when using rbac with AZURE_AUTH_TYPE
param useKeyVault = bool(readEnvironmentVariable('USE_KEY_VAULT', 'true'))
param authType = readEnvironmentVariable('AZURE_AUTH_TYPE', 'keys')

// Deploying using json will set this to "container".
param hostingModel = readEnvironmentVariable('AZURE_APP_SERVICE_HOSTING_MODEL', 'code')

// Feature flags
param azureSearchUseIntegratedVectorization = bool(readEnvironmentVariable('AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION', 'false'))
param azureSearchUseSemanticSearch = bool(readEnvironmentVariable('AZURE_SEARCH_USE_SEMANTIC_SEARCH', 'false'))
param orchestrationStrategy = readEnvironmentVariable('ORCHESTRATION_STRATEGY', 'openai_function')
param logLevel = readEnvironmentVariable('LOGLEVEL', 'INFO')
param recognizedLanguages = readEnvironmentVariable('AZURE_SPEECH_RECOGNIZER_LANGUAGES', 'en-US,fr-FR,de-DE,it-IT')
param conversationFlow = readEnvironmentVariable('CONVERSATION_FLOW', 'custom')

// OpenAI parameters
param azureOpenAIApiVersion = readEnvironmentVariable('AZURE_OPENAI_API_VERSION', '2024-02-01')
param azureOpenAIModel = readEnvironmentVariable('AZURE_OPENAI_MODEL', 'gpt-35-turbo-16k')
param azureOpenAIModelName = readEnvironmentVariable('AZURE_OPENAI_MODEL_NAME', 'gpt-35-turbo-16k')
param azureOpenAIModelVersion = readEnvironmentVariable('AZURE_OPENAI_MODEL_VERSION', '0613')
param azureOpenAIModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_MODEL_CAPACITY', '30'))
param useAdvancedImageProcessing = bool(readEnvironmentVariable('USE_ADVANCED_IMAGE_PROCESSING', 'false'))
param advancedImageProcessingMaxImages = int(readEnvironmentVariable('ADVANCED_IMAGE_PROCESSING_MAX_IMAGES', '1'))
param azureOpenAIVisionModel = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL', 'gpt-4')
param azureOpenAIVisionModelName = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_NAME', 'gpt-4')
param azureOpenAIVisionModelVersion = readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_VERSION', 'vision-preview')
param azureOpenAIVisionModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_VISION_MODEL_CAPACITY', '10'))
param azureOpenAIEmbeddingModelCapacity = int(readEnvironmentVariable('AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY', '30'))
param azureOpenAIEmbeddingModel = readEnvironmentVariable('AZURE_OPENAI_EMBEDDING_MODEL', 'text-embedding-ada-002')
param azureOpenAIEmbeddingModelName = readEnvironmentVariable('AZURE_OPENAI_EMBEDDING_MODEL_NAME', 'text-embedding-ada-002')
param azureOpenAIEmbeddingModelVersion = readEnvironmentVariable('AZURE_OPENAI_EMBEDDING_MODEL_VERSION', '2')
param azureOpenAIMaxTokens = readEnvironmentVariable('AZURE_OPENAI_MAX_TOKENS', '1000')
param azureOpenAITemperature = readEnvironmentVariable('AZURE_OPENAI_TEMPERATURE', '0')
param azureOpenAITopP = readEnvironmentVariable('AZURE_OPENAI_TOP_P', '1')
param azureOpenAIStopSequence = readEnvironmentVariable('AZURE_OPENAI_STOP_SEQUENCE', '\n')
param azureOpenAISystemMessage = readEnvironmentVariable('AZURE_OPENAI_SYSTEM_MESSAGE', 'You are an AI assistant that helps people find information.')
param azureSearchTopK = readEnvironmentVariable('AZURE_SEARCH_TOP_K', '5')

// Computer Vision parameters
param computerVisionLocation = readEnvironmentVariable('AZURE_COMPUTER_VISION_LOCATION', '')
param computerVisionVectorizeImageApiVersion = readEnvironmentVariable('AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION', '2024-02-01')
param computerVisionVectorizeImageModelVersion = readEnvironmentVariable('AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION', '2023-04-15')

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
param storageAccountName = readEnvironmentVariable('AZURE_BLOB_ACCOUNT_NAME', 'str${resourceToken}')
