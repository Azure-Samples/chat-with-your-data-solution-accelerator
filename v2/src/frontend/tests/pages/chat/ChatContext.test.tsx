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
const streamingBot: ChatMessage = {
  id: "s1",
  role: "assistant",
  content: "",
  reasoning: [],
  streaming: true,
};

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

describe("chatReducer streaming actions", () => {
  it("'append_answer' grows the matching message's content", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: "append_answer",
      id: "s1",
      chunk: "hel",
    });
    const b = chatReducer(a, {
      type: "append_answer",
      id: "s1",
      chunk: "lo",
    });
    expect(b.messages).toHaveLength(1);
    expect(b.messages[0].content).toBe("hello");
    // Other messages should be untouched.
  });

  it("'append_answer' is a no-op when the id is unknown", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: "append_answer",
      id: "missing",
      chunk: "x",
    });
    expect(next.messages[0].content).toBe("");
  });

  it("'append_reasoning' pushes onto the matching message's reasoning array", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: "append_reasoning",
      id: "s1",
      chunk: "thinking step 1",
    });
    const b = chatReducer(a, {
      type: "append_reasoning",
      id: "s1",
      chunk: "thinking step 2",
    });
    expect(b.messages[0].reasoning).toEqual([
      "thinking step 1",
      "thinking step 2",
    ]);
  });

  it("'append_reasoning' initializes the array when the seeded message has none", () => {
    // Seed an assistant message that omitted the optional reasoning field.
    const bare: ChatMessage = { id: "b1", role: "assistant", content: "" };
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: bare,
    });
    const next = chatReducer(seeded, {
      type: "append_reasoning",
      id: "b1",
      chunk: "first",
    });
    expect(next.messages[0].reasoning).toEqual(["first"]);
  });

  it("'finish_stream' clears the streaming flag on the matching message", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const next = chatReducer(seeded, { type: "finish_stream", id: "s1" });
    expect(next.messages[0].streaming).toBe(false);
  });

  it("'set_error' attaches an error notice and clears streaming", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: "set_error",
      id: "s1",
      error: "boom",
    });
    expect(next.messages[0].error).toBe("boom");
    expect(next.messages[0].streaming).toBe(false);
  });

  it("does not mutate previous state on streaming actions", () => {
    const seeded = chatReducer(initialChatState, {
      type: "add",
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: "append_answer",
      id: "s1",
      chunk: "x",
    });
    expect(seeded.messages[0].content).toBe("");
    expect(next.messages).not.toBe(seeded.messages);
    expect(next.messages[0]).not.toBe(seeded.messages[0]);
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
