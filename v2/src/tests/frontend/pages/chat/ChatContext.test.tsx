import { describe, expect, it } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import {
  ChatActionType,
  ChatProvider,
  chatReducer,
  initialChatState,
  useChat,
} from "@/pages/chat/ChatContext";
import type { ChatMessage, ChatState, Citation } from "@/models/chat";

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
    const next = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: userMsg,
    });
    expect(next.messages).toEqual([userMsg]);
  });

  it("preserves order across multiple 'add' dispatches", () => {
    const a = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: userMsg,
    });
    const b = chatReducer(a, { type: ChatActionType.Add, message: botMsg });
    expect(b.messages).toEqual([userMsg, botMsg]);
  });

  it("clears messages on 'reset'", () => {
    const populated: ChatState = {
      messages: [userMsg, botMsg],
      focusedCitationId: null,
    };
    expect(chatReducer(populated, { type: ChatActionType.Reset })).toEqual(
      initialChatState,
    );
  });

  it("does not mutate previous state on 'add'", () => {
    const next = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: userMsg,
    });
    expect(initialChatState.messages).toEqual([]);
    expect(next.messages).not.toBe(initialChatState.messages);
  });
});

describe("chatReducer streaming actions", () => {
  it("'append_answer' grows the matching message's content", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: ChatActionType.AppendAnswer,
      id: "s1",
      chunk: "hel",
    });
    const b = chatReducer(a, {
      type: ChatActionType.AppendAnswer,
      id: "s1",
      chunk: "lo",
    });
    expect(b.messages).toHaveLength(1);
    expect(b.messages[0]!.content).toBe("hello");
    // Other messages should be untouched.
  });

  it("'append_answer' is a no-op when the id is unknown", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendAnswer,
      id: "missing",
      chunk: "x",
    });
    expect(next.messages[0]!.content).toBe("");
  });

  it("'append_reasoning' pushes onto the matching message's reasoning array", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: ChatActionType.AppendReasoning,
      id: "s1",
      chunk: "thinking step 1",
    });
    const b = chatReducer(a, {
      type: ChatActionType.AppendReasoning,
      id: "s1",
      chunk: "thinking step 2",
    });
    expect(b.messages[0]!.reasoning).toEqual([
      "thinking step 1",
      "thinking step 2",
    ]);
  });

  it("'append_reasoning' initializes the array when the seeded message has none", () => {
    // Seed an assistant message that omitted the optional reasoning field.
    const bare: ChatMessage = { id: "b1", role: "assistant", content: "" };
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: bare,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendReasoning,
      id: "b1",
      chunk: "first",
    });
    expect(next.messages[0]!.reasoning).toEqual(["first"]);
  });

  it("'finish_stream' clears the streaming flag on the matching message", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.FinishStream,
      id: "s1",
    });
    expect(next.messages[0]!.streaming).toBe(false);
  });

  it("'set_error' attaches an error notice and clears streaming", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetError,
      id: "s1",
      error: "boom",
    });
    expect(next.messages[0]!.error).toBe("boom");
    expect(next.messages[0]!.streaming).toBe(false);
  });

  it("'set_feedback' stores the feedback string on the matching message", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: botMsg,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetFeedback,
      id: "2",
      feedback: "positive",
    });
    expect(next.messages[0]!.feedback).toBe("positive");
  });

  it("'set_feedback' overwrites an existing feedback value", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: { ...botMsg, feedback: "positive" },
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetFeedback,
      id: "2",
      feedback: "negative",
    });
    expect(next.messages[0]!.feedback).toBe("negative");
  });

  it("'set_feedback' clears the feedback value when passed null", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: { ...botMsg, feedback: "positive" },
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetFeedback,
      id: "2",
      feedback: null,
    });
    expect(next.messages[0]!.feedback).toBeNull();
  });

  it("'set_feedback' is a no-op when the id is unknown", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: botMsg,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetFeedback,
      id: "missing",
      feedback: "positive",
    });
    expect(next).toBe(seeded);
  });

  it("'set_feedback' does not touch unrelated message fields", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetFeedback,
      id: "s1",
      feedback: "positive",
    });
    expect(next.messages[0]!.streaming).toBe(true);
    expect(next.messages[0]!.content).toBe("");
    expect(next.messages[0]!.reasoning).toEqual([]);
  });

  it("does not mutate previous state on streaming actions", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendAnswer,
      id: "s1",
      chunk: "x",
    });
    expect(seeded.messages[0]!.content).toBe("");
    expect(next.messages).not.toBe(seeded.messages);
    expect(next.messages[0]).not.toBe(seeded.messages[0]);
  });
});

describe("chatReducer 'append_citation'", () => {
  const cit1: Citation = {
    id: "doc-1",
    title: "Source one",
    url: "https://example.com/1",
    snippet: "first snippet",
    score: 0.91,
    metadata: { kind: "blob" },
  };
  const cit2: Citation = {
    id: "doc-2",
    title: "Source two",
    url: "https://example.com/2",
    snippet: "second snippet",
    score: null,
    metadata: {},
  };

  it("appends a citation onto the matching assistant message", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: cit1,
    });
    expect(next.messages[0]!.citations).toEqual([cit1]);
  });

  it("initializes the citations array when the seeded message has none", () => {
    const bare: ChatMessage = { id: "b1", role: "assistant", content: "" };
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: bare,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "b1",
      citation: cit1,
    });
    expect(next.messages[0]!.citations).toEqual([cit1]);
  });

  it("preserves order across multiple citations", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: cit1,
    });
    const b = chatReducer(a, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: cit2,
    });
    expect(b.messages[0]!.citations).toEqual([cit1, cit2]);
  });

  it("dedupes by citation id so the same source surfaces once", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: cit1,
    });
    const b = chatReducer(a, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: { ...cit1, snippet: "different snippet body" },
    });
    expect(b.messages[0]!.citations).toEqual([cit1]);
  });

  it("is a no-op when the message id is unknown", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "missing",
      citation: cit1,
    });
    expect(next).toBe(seeded);
  });

  it("does not touch unrelated message fields", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.AppendCitation,
      id: "s1",
      citation: cit1,
    });
    expect(next.messages[0]!.streaming).toBe(true);
    expect(next.messages[0]!.content).toBe("");
    expect(next.messages[0]!.reasoning).toEqual([]);
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
      result.current.dispatch({
        type: ChatActionType.Add,
        message: userMsg,
      });
    });
    expect(result.current.state.messages).toEqual([userMsg]);
  });

  it("re-renders consumers when state changes", () => {
    function Probe() {
      const { state, dispatch } = useChat();
      return (
        <div>
          <span data-testid="count">{state.messages.length}</span>
          <button
            onClick={() =>
              dispatch({ type: ChatActionType.Add, message: userMsg })
            }
          >
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

describe("chatReducer 'focus_citation'", () => {
  it("initializes focusedCitationId to null", () => {
    expect(initialChatState.focusedCitationId).toBeNull();
  });

  it("sets focusedCitationId from null to a concrete value", () => {
    const next = chatReducer(initialChatState, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-7",
    });
    expect(next.focusedCitationId).toBe("doc-7");
  });

  it("overwrites a previously focused citation id", () => {
    const a = chatReducer(initialChatState, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    const b = chatReducer(a, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-2",
    });
    expect(b.focusedCitationId).toBe("doc-2");
  });

  it("clears the focused citation id when passed null", () => {
    const focused = chatReducer(initialChatState, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    const cleared = chatReducer(focused, {
      type: ChatActionType.FocusCitation,
      citationId: null,
    });
    expect(cleared.focusedCitationId).toBeNull();
  });

  it("returns the same state reference when the focus value did not change", () => {
    // Reference equality matters for downstream useEffect deps so the
    // panel does not re-fire its open effect on no-op dispatches.
    const focused = chatReducer(initialChatState, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    const same = chatReducer(focused, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    expect(same).toBe(focused);
  });

  it("does not touch the messages array", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: botMsg,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    expect(next.messages).toBe(seeded.messages);
  });

  it("'reset' clears focusedCitationId back to null", () => {
    const focused = chatReducer(initialChatState, {
      type: ChatActionType.FocusCitation,
      citationId: "doc-1",
    });
    const cleared = chatReducer(focused, { type: ChatActionType.Reset });
    expect(cleared.focusedCitationId).toBeNull();
  });
});
