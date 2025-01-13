param keyVaultName string = ''
param storageAccountName string = ''
param azureOpenAIName string = ''
param azureAISearchName string = ''
param rgName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
param speechServiceName string = ''
param computerVisionName string = ''
param postgresServerName string = '' // PostgreSQL server name
param postgresDatabaseName string = 'postgres' // Default database name
param postgresInfoName string = 'AZURE-POSTGRESQL-INFO' // Secret name for PostgreSQL info
param postgresDatabaseAdminUserName string = ''
param storageAccountKeyName string = 'AZURE-STORAGE-ACCOUNT-KEY'
param openAIKeyName string = 'AZURE-OPENAI-API-KEY'
param searchKeyName string = 'AZURE-SEARCH-KEY'
param formRecognizerKeyName string = 'AZURE-FORM-RECOGNIZER-KEY'
param contentSafetyKeyName string = 'AZURE-CONTENT-SAFETY-KEY'
param speechKeyName string = 'AZURE-SPEECH-KEY'
param computerVisionKeyName string = 'AZURE-COMPUTER-VISION-KEY'
param cosmosAccountKeyName string = 'AZURE-COSMOSDB-ACCOUNT-KEY'
param cosmosAccountName string = ''

resource storageAccountKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: storageAccountKeyName
  properties: {
    value: listKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.Storage/storageAccounts', storageAccountName),
      '2021-09-01'
    ).keys[0].value
  }
}

resource openAIKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: openAIKeyName
  properties: {
    value: listKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', azureOpenAIName),
      '2023-05-01'
    ).key1
  }
}

resource searchKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = if (azureAISearchName != '') {
  parent: keyVault
  name: searchKeyName
  properties: {
    value: listAdminKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.Search/searchServices', azureAISearchName),
      '2021-04-01-preview'
    ).primaryKey
  }
}

resource formRecognizerKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: formRecognizerKeyName
  properties: {
    value: listKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', formRecognizerName),
      '2023-05-01'
    ).key1
  }
}

resource contentSafetyKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: contentSafetyKeyName
  properties: {
    value: listKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', contentSafetyName),
      '2023-05-01'
    ).key1
  }
}

resource speechKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: speechKeyName
  properties: {
    value: listKeys(
      resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', speechServiceName),
      '2023-05-01'
    ).key1
  }
}

resource computerVisionKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = if (computerVisionName != '') {
  parent: keyVault
  name: computerVisionKeyName
  properties: {
    value: computerVisionName != ''
      ? listKeys(
          resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', computerVisionName),
          '2023-05-01'
        ).key1
      : ''
  }
}

// Add PostgreSQL info in JSON format
resource postgresInfoSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = if (postgresServerName != '') {
  parent: keyVault
  name: postgresInfoName
  properties: {
    value: postgresServerName != ''
      ? string({
          user: postgresDatabaseAdminUserName
          dbname: postgresDatabaseName
          host: postgresServerName
        })
      : ''
  }
}

// Conditional CosmosDB key secret
resource cosmosDbAccountKey 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = if (cosmosAccountName != '') {
  parent: keyVault
  name: cosmosAccountKeyName
  properties: {
    value: cosmosAccountName != ''
      ? listKeys(
          resourceId(subscription().subscriptionId, rgName, 'Microsoft.DocumentDB/databaseAccounts', cosmosAccountName),
          '2022-08-15'
        ).primaryMasterKey
      : ''
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

output CONTENT_SAFETY_KEY_NAME string = contentSafetyKeySecret.name
output FORM_RECOGNIZER_KEY_NAME string = formRecognizerKeySecret.name
output SEARCH_KEY_NAME string = azureAISearchName != '' ? searchKeySecret.name : ''
output OPENAI_KEY_NAME string = openAIKeySecret.name
output STORAGE_ACCOUNT_KEY_NAME string = storageAccountKeySecret.name
output SPEECH_KEY_NAME string = speechKeySecret.name
output COMPUTER_VISION_KEY_NAME string = computerVisionName != '' ? computerVisionKeySecret.name : ''
output COSMOS_ACCOUNT_KEY_NAME string = cosmosAccountName != '' ? cosmosDbAccountKey.name : ''
output POSTGRESQL_INFO_NAME string = postgresServerName != '' ? postgresInfoSecret.name : ''
