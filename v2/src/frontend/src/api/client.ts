import type { AskResponse, ChatMessage, FrontendSettings } from "./models";

const API_BASE = "";

async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options?.headers,
        },
    });
    if (!response.ok) {
        const error = await response.text();
        throw new Error(error || `HTTP ${response.status}`);
    }
    return response.json();
}

export async function postConversation(
    messages: ChatMessage[],
    conversationId?: string
): Promise<AskResponse> {
    return fetchApi<AskResponse>("/api/conversation", {
        method: "POST",
        body: JSON.stringify({ messages, conversation_id: conversationId }),
    });
}

export async function postConversationStream(
    messages: ChatMessage[],
    conversationId?: string,
    signal?: AbortSignal
): Promise<Response> {
    return fetch(`${API_BASE}/api/conversation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            messages,
            conversation_id: conversationId,
        }),
        signal,
    });
}

export async function getHistoryList(): Promise<Array<Record<string, unknown>>> {
    return fetchApi("/api/history/list");
}

export async function getFrontendSettings(): Promise<FrontendSettings> {
    return fetchApi("/api/history/frontend_settings");
}

export async function getSpeechToken(): Promise<{ token: string; region: string }> {
    return fetchApi("/api/speech");
}
