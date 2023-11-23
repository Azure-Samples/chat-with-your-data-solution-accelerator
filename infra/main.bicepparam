using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME')

param location = readEnvironmentVariable('AZURE_LOCATION')

param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

param useKeyVault = readEnvironmentVariable('USE_KEY_VAULT')
