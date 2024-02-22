[Back to *Chat with your data* README](../README.md)

# Azure Deployment

## Azure Resource Manager
Click the following deployment button to create the required resources for this accelerator directly in your Azure Subscription. 

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fchat-with-your-data-solution-accelerator%2Fmain%2Finfra%2Fmain.json) 

This requires the following fields to be entered:
   
|Field  |Description  |
|---------|---------|
|Resource group   | The resource group that will contain the resources for this accelerator. You can select **Create new** to create a new group.        |
|Resource prefix   | A text string that will be appended to each resource that gets created, and used as the website name for the web app. This name cannot contain spaces or special characters.        |
|Orchestration strategy| Use Azure OpenAI Functions (openai_functions) or LangChain (langchain) for messages orchestration. If you are using a new model version 0613 select "openai_functions" (or "langchain"), if you are using a 0314 model version select "langchain"|

## Bicep

A [Bicep file](./infra/main.bicep) is used to generate the [ARM template](./infra/main.json). You can deploy this accelerator by the following command

```sh
RESOURCE_GROUP_NAME=cwyd
az group create --location uksouth --resource-group $RESOURCE_GROUP_NAME
az deployment group create --resource-group $RESOURCE_GROUP_NAME --template-file ./infra/main.bicep
 ```
