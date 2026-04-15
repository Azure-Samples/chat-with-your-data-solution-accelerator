import { create } from "zustand";
import type { ChatMessage } from "../api/models";

interface ChatState {
    messages: ChatMessage[];
    conversationId: string | null;
    isLoading: boolean;
    isGenerating: boolean;
    error: string | null;

    addMessage: (message: ChatMessage) => void;
    setMessages: (messages: ChatMessage[]) => void;
    setConversationId: (id: string | null) => void;
    setIsLoading: (loading: boolean) => void;
    setIsGenerating: (generating: boolean) => void;
    setError: (error: string | null) => void;
    reset: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
    messages: [],
    conversationId: null,
    isLoading: false,
    isGenerating: false,
    error: null,

    addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),
    setMessages: (messages) => set({ messages }),
    setConversationId: (id) => set({ conversationId: id }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    setIsGenerating: (generating) => set({ isGenerating: generating }),
    setError: (error) => set({ error }),
    reset: () =>
        set({
            messages: [],
            conversationId: null,
            isLoading: false,
            isGenerating: false,
            error: null,
        }),
}));
