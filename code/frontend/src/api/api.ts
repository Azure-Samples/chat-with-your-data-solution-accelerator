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

    return response;
}
