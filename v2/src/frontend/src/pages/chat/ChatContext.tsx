/**
 * Pillar: Stable Core
 * Phase: 2
 *
 * Chat domain state. Single React Context + useReducer per the v2 frontend
 * conventions (no Zustand, no Redux). Consumers must wrap their tree in
 * <ChatProvider> and read state via useChat(); calling useChat() outside the
 * provider throws so misuse fails fast.
 */
import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
}

export interface ChatState {
  messages: ChatMessage[];
}

export type ChatAction =
  | { type: "add"; message: ChatMessage }
  | { type: "reset" };

export const initialChatState: ChatState = { messages: [] };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "add":
      return { ...state, messages: [...state.messages, action.message] };
    case "reset":
      return initialChatState;
  }
}

interface ChatContextValue {
  state: ChatState;
  dispatch: Dispatch<ChatAction>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (ctx === null) {
    throw new Error("useChat must be used within a <ChatProvider>");
  }
  return ctx;
}
