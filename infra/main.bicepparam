using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME')

param Location = readEnvironmentVariable('AZURE_LOCATION')
