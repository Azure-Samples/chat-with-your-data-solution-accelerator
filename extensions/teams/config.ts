const config = {
  botId: process.env.BOT_ID,
  botPassword: process.env.BOT_PASSWORD,
  azureFunctionUrl: process.env.AZURE_FUNCTION_URL,
  azureAppApiBaseUrl: process.env.AZURE_APP_API_BASE_URL,
  tenantId: process.env.TEAMS_APP_TENANT_ID,
  getFileEndpoint: process.env.AZURE_APP_API_BASE_URL ?
    `${process.env.AZURE_APP_API_BASE_URL}api/files` :
    null,
};

export default config;
