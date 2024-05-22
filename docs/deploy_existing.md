
# Deploying with existing Azure resources

If you already have existing Azure resources, or if you want to specify the exact name of new Azure Resource, you can do so by setting `azd` environment values.
You should set these values before running `azd up`. Once you've set them, return to the [deployment steps](../README.md#deploy).

* [Resource group](#resource-group)
* [OpenAI resource](#openai-resource)
* [Azure AI Search resource](#azure-ai-search-resource)
* [Azure App Service Plan and App Service resources](#azure-app-service-plan-and-app-service-resources)
* [Azure Application Insights and related resources](#azure-application-insights-and-related-resources)
* [Azure Computer Vision resources](#azure-computer-vision-resources)
* [Azure Document Intelligence resource](#azure-document-intelligence-resource)
* [Other Azure resources](#other-azure-resources)


## Resource group

1. Run `azd env set AZURE_RESOURCE_GROUP {Name of existing resource group}`
1. Run `azd env set AZURE_LOCATION {Location of existing resource group}`

## OpenAI resource

### Azure OpenAI:

1. Run `azd env set AZURE_OPENAI_RESOURCE {Name of existing OpenAI service}`

### Openai.com OpenAI:

1. Run `azd env set OPENAI_HOST openai`
2. Run `azd env set OPENAI_ORGANIZATION {Your OpenAI organization}`
3. Run `azd env set AZURE_OPENAI_API_KEY {Your OpenAI API key}`
4. Run `azd up`

You can retrieve your OpenAI key by checking [your user page](https://platform.openai.com/account/api-keys) and your organization by navigating to [your organization page](https://platform.openai.com/account/org-settings).
Learn more about creating an OpenAI free trial at [this link](https://openai.com/pricing).
Do *not* check your key into source control.

## Azure AI Search resource

1. Run `azd env set AZURE_SEARCH_SERVICE {Name of existing Azure AI Search service}`
1. If you have an existing index that is set up with all the expected fields, then run `azd env set AZURE_SEARCH_INDEX {Name of existing index}`. Otherwise, the `azd up` command will create a new index.

## Azure Computer Vision resources

1. Run `azd env set AZURE_COMPUTER_VISION_ENDPOINT {Name of existing Azure Computer Vision Service Name}`

## Other Azure resources

You can also use existing Azure AI Storage Accounts. See `./infra/main.parameters.json` for list of environment variables to pass to `azd env set` to configure those existing resources.
