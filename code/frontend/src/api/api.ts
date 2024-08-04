import { ConversationRequest } from "./models";


export async function callConversationApi(options: ConversationRequest, abortSignal: AbortSignal): Promise<Response> {
    const response = await fetch("/api/conversation", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            messages: options.messages,
            conversation_id: options.id
        }),
        signal: abortSignal
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData.error));
    }

    return response;
}

export async function getAssistantTypeApi() {
    try {
        const response = await fetch("/api/assistanttype", {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            },
        });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const config = await response.json(); // Parse JSON response
      return config;
    } catch (error) {
      console.error('Failed to fetch configuration:', error);
      return null; // Return null or some default value in case of error
    }
  }
