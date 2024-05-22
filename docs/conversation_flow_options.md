# Conversation Flow Options

The backend service for 'Chat With Your Data' supports both 'custom' and 'On Your Data' conversation flows.

## Configuration

To switch between the two conversation flows, you can set the `CONVERSATION_FLOW` environment variable to either `custom` or `byod`.

When running locally, you can set the environment variable in the `.env` file.

## Options

### Custom

```env
CONVERSATION_FLOW=custom
```

Provides the option to use a custom orchestrator to handle the conversation flow. 'Chat With Your Data' provides support for the following orchestrators:

- [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/)
- [Langchain](https://python.langchain.com/v0.2/docs/introduction/)
- [OpenAI Function](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)

### 'On Your Data'

```env
CONVERSATION_FLOW=byod
```

With `CONVERSATION_FLOW` set to "byod", the backend service will mimic the [On Your Data](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/use-your-data) flow.

'On Your Data' enables you to run advanced AI models such as GPT-35-Turbo and GPT-4 on your own enterprise data without needing to train or fine-tune models. You can chat on top of and analyze your data with greater accuracy. You can specify sources to support the responses based on the latest information available in your designated data sources.
