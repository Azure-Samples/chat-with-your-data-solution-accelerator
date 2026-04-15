import { create } from "zustand";

interface Conversation {
    id: string;
    title: string;
    date: string;
}

interface HistoryState {
    conversations: Conversation[];
    isLoading: boolean;
    isOpen: boolean;

    setConversations: (conversations: Conversation[]) => void;
    setIsLoading: (loading: boolean) => void;
    toggleOpen: () => void;
    setOpen: (open: boolean) => void;
}

export const useHistoryStore = create<HistoryState>((set) => ({
    conversations: [],
    isLoading: false,
    isOpen: false,

    setConversations: (conversations) => set({ conversations }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
    setOpen: (open) => set({ isOpen: open }),
}));
