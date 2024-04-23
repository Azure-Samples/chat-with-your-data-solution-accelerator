# Implement a PromptFlow Orchestration as an alternative for the chat backend

* **Status:** proposed
* **Proposer:** @superhindupur
* **Date:** 2024-04-23
* **Technical Story:** [Include a prompt flow integration](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/406)

## Context and Problem Statement

The chat functionality in this repo has an orchestraction mechanism for fetching the answer based on the user's question - the question is sent to the LLM, then based on whether it needs to be searched, it goes to the search service before the answer is finally reprocessed and sent back to the user on the chat UI.

This orchestration between the chat backend, LLM and search service is done inside code and currently has two options for orchestration management - openai functions and langchain (controlled by the deployment bicep param `orchestrationStrategy`). In this ADR, we explore whether it is worth adding a third mechanism to orchestrate the chat backend functionality with [Azure Machine Learning PromptFlow](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

## Decision Drivers

* Being able to demonstrate various orchestration options to customers
* Limiting complexity in the repo
* Ease of maintenance of the PromptFlow configuration

## Considered Options

* Adding the PromptFlow orchestration
* Not adding the PromptFlow orchestration

## Decision Outcome
In the absence of concrete business / customer requirements, the outcome is to NOT add a PromptFlow orchestrator alternative for the chat backend.


## Pros and Cons of the Options

### Adding the PromptFlow orchestration
* Good, because customers wanting to deploy the chat backend as a PromptFlow endpoint will be able to do so.
* Good, because customers will have a low-code mechanism to experiment with the orchestration of the chat backend.
* Bad, because building a PromptFlow orchestration that mimics the current chat backend requires significant effort - and it is unclear how much customer demand we have for it.
* Bad, because the PromptFlow configuration can get out of date with the other orchestrators that are in code. This will cause confusion to customers and will lead them to open issues against the repo.
* Bad, because outside of end-to-end tests that test an actual deployment, there is no way to test the PromptFlow configuration (i.e., no way to unit-test it).


### Not adding the PromptFlow Orchestration
* Bad, because customers wanting to deploy the chat backend as a PromptFlow endpoint will NOT be able to do so.
* Bad, because in the absence of a low-code PromptFlow alternative, customers will need coding knowledge to experiment with the chat backend orchestration.
* Good, because there's one less thing to maintain / explain / test in the repo. :)
