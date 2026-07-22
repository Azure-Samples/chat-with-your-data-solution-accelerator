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
      conversationId: "conv-1",
      focusedCitationId: null,
      activeCitation: null,
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

  it("'set_reasoning_placeholder' sets the placeholder without touching reasoning", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetReasoningPlaceholder,
      id: "s1",
      text: "Searching the knowledge base for relevant sources\u2026",
    });
    expect(next.messages[0]!.reasoningPlaceholder).toBe(
      "Searching the knowledge base for relevant sources\u2026",
    );
    expect(next.messages[0]!.reasoning).toEqual([]);
  });

  it("'set_reasoning_placeholder' replaces (does not append) on repeat dispatch", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: streamingBot,
    });
    const a = chatReducer(seeded, {
      type: ChatActionType.SetReasoningPlaceholder,
      id: "s1",
      text: "first hint",
    });
    const b = chatReducer(a, {
      type: ChatActionType.SetReasoningPlaceholder,
      id: "s1",
      text: "second hint",
    });
    expect(b.messages[0]!.reasoningPlaceholder).toBe("second hint");
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

describe("chatReducer citation detail panel", () => {
  const citation: Citation = {
    id: "[doc1]",
    title: "Benefit_Options.pdf",
    url: "https://example.test/benefit-options.pdf",
    snippet: "**Health** coverage details.",
    score: null,
    metadata: {},
  };

  it("initializes activeCitation to null", () => {
    expect(initialChatState.activeCitation).toBeNull();
  });

  it("sets activeCitation on 'show_citation'", () => {
    const next = chatReducer(initialChatState, {
      type: ChatActionType.ShowCitation,
      citation,
    });
    expect(next.activeCitation).toEqual(citation);
  });

  it("replaces an already-shown citation on a second 'show_citation'", () => {
    const other: Citation = { ...citation, id: "[doc2]", title: "Other.pdf" };
    const a = chatReducer(initialChatState, {
      type: ChatActionType.ShowCitation,
      citation,
    });
    const b = chatReducer(a, {
      type: ChatActionType.ShowCitation,
      citation: other,
    });
    expect(b.activeCitation).toEqual(other);
  });

  it("clears activeCitation on 'close_citation'", () => {
    const shown = chatReducer(initialChatState, {
      type: ChatActionType.ShowCitation,
      citation,
    });
    const closed = chatReducer(shown, { type: ChatActionType.CloseCitation });
    expect(closed.activeCitation).toBeNull();
  });

  it("returns the same state reference when closing an already-closed panel", () => {
    const closed = chatReducer(initialChatState, {
      type: ChatActionType.CloseCitation,
    });
    expect(closed).toBe(initialChatState);
  });

  it("does not touch the messages array on 'show_citation'", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: botMsg,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.ShowCitation,
      citation,
    });
    expect(next.messages).toBe(seeded.messages);
  });

  it("'reset' clears activeCitation back to null", () => {
    const shown = chatReducer(initialChatState, {
      type: ChatActionType.ShowCitation,
      citation,
    });
    const cleared = chatReducer(shown, { type: ChatActionType.Reset });
    expect(cleared.activeCitation).toBeNull();
  });
});

describe("chatReducer conversation tracking", () => {
  it("initializes conversationId to null", () => {
    expect(initialChatState.conversationId).toBeNull();
  });

  it("'set_conversation_id' sets the id from null", () => {
    const next = chatReducer(initialChatState, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-1",
    });
    expect(next.conversationId).toBe("conv-1");
  });

  it("'set_conversation_id' overwrites an existing id", () => {
    const a = chatReducer(initialChatState, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-1",
    });
    const b = chatReducer(a, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-2",
    });
    expect(b.conversationId).toBe("conv-2");
  });

  it("'set_conversation_id' clears the id when passed null", () => {
    const set = chatReducer(initialChatState, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-1",
    });
    const cleared = chatReducer(set, {
      type: ChatActionType.SetConversationId,
      conversationId: null,
    });
    expect(cleared.conversationId).toBeNull();
  });

  it("'set_conversation_id' does not touch the messages array", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: userMsg,
    });
    const next = chatReducer(seeded, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-1",
    });
    expect(next.messages).toBe(seeded.messages);
  });

  it("'load_conversation' replaces the transcript and sets the id", () => {
    const seeded = chatReducer(initialChatState, {
      type: ChatActionType.Add,
      message: { id: "old", role: "user", content: "stale" },
    });
    const loaded = chatReducer(seeded, {
      type: ChatActionType.LoadConversation,
      conversationId: "conv-9",
      messages: [userMsg, botMsg],
    });
    expect(loaded.conversationId).toBe("conv-9");
    expect(loaded.messages).toEqual([userMsg, botMsg]);
  });

  it("'load_conversation' rehydrates citations carried on the loaded messages", () => {
    const citation: Citation = {
      id: "doc-1",
      title: "Loaded source",
      url: "https://example.com/loaded",
      snippet: "rehydrated snippet",
      score: 0.5,
      metadata: {},
    };
    const assistantWithCitations: ChatMessage = {
      id: "a1",
      role: "assistant",
      content: "answer with a source",
      citations: [citation],
    };
    const loaded = chatReducer(initialChatState, {
      type: ChatActionType.LoadConversation,
      conversationId: "conv-9",
      messages: [userMsg, assistantWithCitations],
    });
    expect(loaded.messages[1]!.citations).toEqual([citation]);
  });

  it("'load_conversation' clears citation UI from the prior conversation", () => {
    const prior: ChatState = {
      messages: [botMsg],
      conversationId: "conv-1",
      focusedCitationId: "doc-1",
      activeCitation: {
        id: "doc-1",
        title: "Prior",
        url: "https://example.com/prior",
        snippet: "prior",
        score: null,
        metadata: {},
      },
    };
    const loaded = chatReducer(prior, {
      type: ChatActionType.LoadConversation,
      conversationId: "conv-2",
      messages: [userMsg],
    });
    expect(loaded.focusedCitationId).toBeNull();
    expect(loaded.activeCitation).toBeNull();
  });

  it("'reset' clears conversationId back to null", () => {
    const set = chatReducer(initialChatState, {
      type: ChatActionType.SetConversationId,
      conversationId: "conv-1",
    });
    const cleared = chatReducer(set, { type: ChatActionType.Reset });
    expect(cleared.conversationId).toBeNull();
  });
});
