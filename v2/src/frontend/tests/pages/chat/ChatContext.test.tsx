import { describe, expect, it } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import {
  ChatProvider,
  chatReducer,
  initialChatState,
  useChat,
  type ChatMessage,
} from "../../../src/pages/chat/ChatContext";

const userMsg: ChatMessage = { id: "1", role: "user", content: "hello" };
const botMsg: ChatMessage = { id: "2", role: "assistant", content: "hi" };

describe("chatReducer", () => {
  it("appends a message on 'add'", () => {
    const next = chatReducer(initialChatState, { type: "add", message: userMsg });
    expect(next.messages).toEqual([userMsg]);
  });

  it("preserves order across multiple 'add' dispatches", () => {
    const a = chatReducer(initialChatState, { type: "add", message: userMsg });
    const b = chatReducer(a, { type: "add", message: botMsg });
    expect(b.messages).toEqual([userMsg, botMsg]);
  });

  it("clears messages on 'reset'", () => {
    const populated = { messages: [userMsg, botMsg] };
    expect(chatReducer(populated, { type: "reset" })).toEqual(initialChatState);
  });

  it("does not mutate previous state on 'add'", () => {
    const next = chatReducer(initialChatState, { type: "add", message: userMsg });
    expect(initialChatState.messages).toEqual([]);
    expect(next.messages).not.toBe(initialChatState.messages);
  });
});

describe("useChat", () => {
  it("throws when used outside <ChatProvider>", () => {
    const orig = console.error;
    console.error = () => {};
    try {
      expect(() => renderHook(() => useChat())).toThrow(
        /must be used within a <ChatProvider>/,
      );
    } finally {
      console.error = orig;
    }
  });

  it("exposes state and dispatch inside <ChatProvider>", () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider });
    expect(result.current.state).toEqual(initialChatState);
    act(() => {
      result.current.dispatch({ type: "add", message: userMsg });
    });
    expect(result.current.state.messages).toEqual([userMsg]);
  });

  it("re-renders consumers when state changes", () => {
    function Probe() {
      const { state, dispatch } = useChat();
      return (
        <div>
          <span data-testid="count">{state.messages.length}</span>
          <button onClick={() => dispatch({ type: "add", message: userMsg })}>
            add
          </button>
        </div>
      );
    }
    render(
      <ChatProvider>
        <Probe />
      </ChatProvider>,
    );
    expect(screen.getByTestId("count").textContent).toBe("0");
    act(() => {
      screen.getByText("add").click();
    });
    expect(screen.getByTestId("count").textContent).toBe("1");
  });
});
