/**
 * Pillar: Stable Core
 * Phase: 5 (FE bridge — dev_plan §4 task #24, FE half)
 *
 * Chat domain state. Single React Context + useReducer per the v2 frontend
 * conventions (no Zustand, no Redux). Consumers must wrap their tree in
 * <ChatProvider> and read state via useChat(); calling useChat() outside the
 * provider throws so misuse fails fast.
 *
 * Phase 5 extension: assistant messages now carry a `reasoning: string[]`
 * array (one entry per `reasoning` SSE frame) and a transient `streaming`
 * flag toggled while a `streamChat()` iterator is in flight. The reducer
 * gains four streaming actions (`append_answer`, `append_reasoning`,
 * `finish_stream`, `set_error`) that target a single message by id so
 * `MessageInput` can fold SSE events from `api/streamChat` into the live
 * transcript without juggling local state.
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
  /** Reasoning frames collected from the SSE feed. Empty/absent for user msgs. */
  reasoning?: string[];
  /** True while an SSE stream is actively appending to this message. */
  streaming?: boolean;
  /** Inline error notice from a `channel: "error"` SSE frame. */
  error?: string;
  /**
   * Persisted feedback value for this message, mirrored from
   * `MessageRecord.feedback`. `null` (or absent) means the user has not
   * submitted feedback yet; a non-empty string is the freeform value the
   * backend stored (e.g. `"positive"`, `"negative"`, or a structured
   * reason payload). `<FeedbackButtons>` reads this to drive the
   * selected-state visualization.
   */
  feedback?: string | null;
}

export interface ChatState {
  messages: ChatMessage[];
}

export type ChatAction =
  | { type: "add"; message: ChatMessage }
  | { type: "append_answer"; id: string; chunk: string }
  | { type: "append_reasoning"; id: string; chunk: string }
  | { type: "finish_stream"; id: string }
  | { type: "set_error"; id: string; error: string }
  | { type: "set_feedback"; id: string; feedback: string | null }
  | { type: "reset" };

export const initialChatState: ChatState = { messages: [] };

function mapMessage(
  state: ChatState,
  id: string,
  update: (m: ChatMessage) => ChatMessage,
): ChatState {
  let touched = false;
  const next = state.messages.map((m) => {
    if (m.id !== id) return m;
    touched = true;
    return update(m);
  });
  if (!touched) return state;
  return { ...state, messages: next };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "add":
      return { ...state, messages: [...state.messages, action.message] };
    case "append_answer":
      return mapMessage(state, action.id, (m) => ({
        ...m,
        content: m.content + action.chunk,
      }));
    case "append_reasoning":
      return mapMessage(state, action.id, (m) => ({
        ...m,
        reasoning: [...(m.reasoning ?? []), action.chunk],
      }));
    case "finish_stream":
      return mapMessage(state, action.id, (m) => ({ ...m, streaming: false }));
    case "set_error":
      return mapMessage(state, action.id, (m) => ({
        ...m,
        streaming: false,
        error: action.error,
      }));
    case "set_feedback":
      return mapMessage(state, action.id, (m) => ({
        ...m,
        feedback: action.feedback,
      }));
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
