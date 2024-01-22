using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'env_name')

param location = readEnvironmentVariable('AZURE_LOCATION', 'location')

param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', 'principal_id')

// Please make sure to set this value to false when using rbac with AUTH_TYPE
param useKeyVault = bool(readEnvironmentVariable('USE_KEY_VAULT', 'false'))

param authType = readEnvironmentVariable('AUTH_TYPE', 'rbac')
