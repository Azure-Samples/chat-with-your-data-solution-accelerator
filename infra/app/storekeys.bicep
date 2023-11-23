param keyVaultName string = ''
param storageAccountName string = ''
param azureOpenAIName string = ''
param azureCognitiveSearchName string = ''
param rgName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''

resource storageAccountKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'storageAccountKey'
  properties: {
    value: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
  }
}

resource openAIKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'openAIKey'
  properties: {
    value: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
  }
}

resource searchKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'searchKey'
  properties: {
    value: listAdminKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Search/searchServices', azureCognitiveSearchName), '2021-04-01-preview').primaryKey
  }
}

resource formRecognizerKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'formRecognizerKey'
  properties: {
    value: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
  }
}

resource contentSafetyKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'contentSafetyKey'
  properties: {
    value: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

output CONTENT_SAFETY_KEY string = contentSafetyKeySecret.name
output FORM_RECOGNIZER_KEY string = formRecognizerKeySecret.name
output SEARCH_KEY string = searchKeySecret.name
output OPENAI_KEY string = openAIKeySecret.name
output STORAGE_ACCOUNT_KEY string = storageAccountKeySecret.name
