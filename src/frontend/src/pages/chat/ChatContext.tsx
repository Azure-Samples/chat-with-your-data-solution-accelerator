/**
 * Chat domain state. Single React Context + useReducer per the v2 frontend
 * conventions (no Zustand, no Redux). Consumers must wrap their tree in
 * <ChatProvider> and read state via useChat(); calling useChat() outside the
 * provider throws so misuse fails fast.
 *
 * Assistant messages carry a `reasoning: string[]` array (one entry per
 * `reasoning` SSE frame) and a transient `streaming` flag toggled while a
 * `streamChat()` iterator is in flight. The reducer has four streaming
 * actions (`append_answer`, `append_reasoning`, `finish_stream`,
 * `set_error`) that target a single message by id so `MessageInput` can
 * fold SSE events from `api/streamChat` into the live transcript without
 * juggling local state.
 */
import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type { ChatMessage, ChatState, Citation } from "@/models/chat";

export const ChatActionType = {
  Add: "add",
  AppendAnswer: "append_answer",
  AppendReasoning: "append_reasoning",
  SetReasoningPlaceholder: "set_reasoning_placeholder",
  AppendCitation: "append_citation",
  FinishStream: "finish_stream",
  SetError: "set_error",
  FocusCitation: "focus_citation",
  ShowCitation: "show_citation",
  CloseCitation: "close_citation",
  SetConversationId: "set_conversation_id",
  LoadConversation: "load_conversation",
  Reset: "reset",
} as const;
export type ChatActionType =
  (typeof ChatActionType)[keyof typeof ChatActionType];

export type ChatAction =
  | { type: typeof ChatActionType.Add; message: ChatMessage }
  | { type: typeof ChatActionType.AppendAnswer; id: string; chunk: string }
  | { type: typeof ChatActionType.AppendReasoning; id: string; chunk: string }
  | {
      type: typeof ChatActionType.SetReasoningPlaceholder;
      id: string;
      text: string;
    }
  | { type: typeof ChatActionType.AppendCitation; id: string; citation: Citation }
  | { type: typeof ChatActionType.FinishStream; id: string }
  | { type: typeof ChatActionType.SetError; id: string; error: string }
  | { type: typeof ChatActionType.FocusCitation; citationId: string | null }
  | { type: typeof ChatActionType.ShowCitation; citation: Citation }
  | { type: typeof ChatActionType.CloseCitation }
  | {
      type: typeof ChatActionType.SetConversationId;
      conversationId: string | null;
    }
  | {
      type: typeof ChatActionType.LoadConversation;
      conversationId: string;
      messages: ChatMessage[];
    }
  | { type: typeof ChatActionType.Reset };

export const initialChatState: ChatState = {
  messages: [],
  conversationId: null,
  focusedCitationId: null,
  activeCitation: null,
};

function mapMessage(
  state: ChatState,
  id: string,
  update: (m: ChatMessage) => ChatMessage,
): ChatState {
  const index = state.messages.findIndex((m) => m.id === id);
  if (index === -1) return state;
  const next = state.messages.map((m, i) => (i === index ? update(m) : m));
  return { ...state, messages: next };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case ChatActionType.Add:
      return { ...state, messages: [...state.messages, action.message] };
    case ChatActionType.AppendAnswer:
      return mapMessage(state, action.id, (m) => ({
        ...m,
        content: m.content + action.chunk,
      }));
    case ChatActionType.AppendReasoning:
      return mapMessage(state, action.id, (m) => ({
        ...m,
        reasoning: [...(m.reasoning ?? []), action.chunk],
      }));
    case ChatActionType.SetReasoningPlaceholder:
      // Replaces (never appends): the transient retrieval narration is one
      // line, shown only until real reasoning frames land in `reasoning`.
      return mapMessage(state, action.id, (m) => ({
        ...m,
        reasoningPlaceholder: action.text,
      }));
    case ChatActionType.AppendCitation:
      return mapMessage(state, action.id, (m) => {
        const existing = m.citations ?? [];
        if (existing.some((c) => c.id === action.citation.id)) {
          // Same source can be cited across multiple answer chunks;
          // dedupe at the reducer so the panel renders one section
          // per unique source even when the wire emits duplicates.
          return m;
        }
        return { ...m, citations: [...existing, action.citation] };
      });
    case ChatActionType.FinishStream:
      return mapMessage(state, action.id, (m) => ({ ...m, streaming: false }));
    case ChatActionType.SetError:
      return mapMessage(state, action.id, (m) => ({
        ...m,
        streaming: false,
        error: action.error,
      }));
    case ChatActionType.FocusCitation:
      // No-op when the focus value is already the active one. Keeps
      // reference equality stable for downstream useEffect deps so
      // the same token-click does not re-fire the panel open effect.
      if (state.focusedCitationId === action.citationId) return state;
      return { ...state, focusedCitationId: action.citationId };
    case ChatActionType.ShowCitation:
      return { ...state, activeCitation: action.citation };
    case ChatActionType.CloseCitation:
      // No-op when the detail column is already closed so a redundant
      // dismiss does not churn reference equality for consumers.
      if (state.activeCitation === null) return state;
      return { ...state, activeCitation: null };
    case ChatActionType.SetConversationId:
      return { ...state, conversationId: action.conversationId };
    case ChatActionType.LoadConversation:
      // Replace the transcript wholesale and clear the per-conversation
      // citation UI (focused token + detail column) so a freshly loaded
      // thread starts clean. Each loaded message carries its own
      // citations, so the reference panels rehydrate from the message
      // list with no extra wiring.
      return {
        ...initialChatState,
        conversationId: action.conversationId,
        messages: action.messages,
      };
    case ChatActionType.Reset:
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
