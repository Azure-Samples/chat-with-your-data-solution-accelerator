export interface ChatMessage {
    role: "user" | "assistant" | "system" | "tool" | "error";
    content: string;
    id?: string;
    date?: string;
    feedback?: string;
}

export interface Citation {
    content: string;
    title: string;
    url: string;
    filepath: string;
    chunk_id: string;
}

export interface AskResponse {
    id: string;
    choices: Array<{
        messages: ChatMessage[];
    }>;
}

export interface FrontendSettings {
    CHAT_HISTORY_ENABLED: boolean;
    FEEDBACK_ENABLED: boolean;
}
