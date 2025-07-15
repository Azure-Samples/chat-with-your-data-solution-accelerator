param keyVaultName string
param clientkey string

resource clientKeySecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'FUNCTION-KEY'
  properties: {
    value: clientkey
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

output FUNCTION_KEY string = clientKeySecret.name
