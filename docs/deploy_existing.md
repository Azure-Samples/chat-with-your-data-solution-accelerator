[Back to *Chat with your data* README](../README.md)

# Deploying with existing Azure resources

If you already have existing Azure resources, or if you want to specify the exact name of new Azure Resource, you can do so by setting `azd` environment values.
You should set these values before running `azd up`. Use the following command to create a new environment
```sh
azd env new <myNewEnvironment>
```

The following lists the resources that you can set to existing resources. If you miss any out, the deployment will create new resources.

- Run `azd env set AZURE_RESOURCE_GROUP {Name of existing resource group}`
- Run `azd env set AZURE_LOCATION {Location of existing resource group}`
- Run `azd env set AZURE_BLOB_ACCOUNT_NAME {Name of storage account}`
- Run `azd env set AZURE_KEY_VAULT_NAME {Name of the Key vault to store the secrets}`
- Run `azd env set AZURE_OPENAI_RESOURCE {Name of existing OpenAI service}`
- Run `azd env set AZURE_OPENAI_API_KEY {Your OpenAI API key}`
- Run `azd env set AZURE_SEARCH_SERVICE {Name of existing Azure AI Search service}`
- Run `azd env set AZURE_SPEECH_SERVICE_NAME {Name of the Speech Service }` (Optional)
- Run `azd env set AZURE_FORM_RECOGNIZER_ENDPOINT {Uri of the endpoint}`
- Run `azd env set AZURE_COMPUTER_VISION_ENDPOINT {Name of existing Azure Computer Vision Service Name}`

- If you have an existing index that is set up with all the expected fields, then run `azd env set AZURE_SEARCH_INDEX {Name of existing index}`. Run `azd env set AZURE_SEARCH_INDEXER_NAME {Name of existing indexer}`

Otherwise, the `azd up` command will create a new index.


## Other Azure resources

You can also use existing Azure AI Storage Accounts. See `./infra/main.parameters.json` for list of environment variables to pass to `azd env set` to configure those existing resources.

## Deploy
- Run `azd up`

Once you've set them, return to the [deployment steps](../README.md#deploy).
