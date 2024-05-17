# Prompt Flow

This is a spike on integrating Prompt Flow as an orchestrator option to the Chat With Your Data Solution Accelerator.


## Setup

1. `cd docs/spikes/prompt-flow/flow/`
1. `pip install -r requirements`
2. Update connection files in [flow/connections](flow/connections/) with the host of your instances
3. `pf connection create -f connections/AISearch.yml`
4. `pf connection create -f connections/AzureOpenAIConnection.yml`

## To run locally

1. `OPENAI_CONNECTION_API_KEY=<key> AISEARCH_CONNECTION_API_KEY=<key> pf flow test --flow . --ui`


# To build
1. `pf flow build --source . --output dist-executable --format executable`
