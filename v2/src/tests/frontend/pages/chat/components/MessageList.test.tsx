import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
} from "@/pages/chat/ChatContext";
import { MessageList } from "@/pages/chat/components/MessageList";
import type { ChatMessage } from "@/models/chat";

// Capture every dispatchToast() call across the suite so error-toast
// wiring can be asserted without standing up the real Fluent Toaster
// portal in jsdom. All other Fluent exports pass through unchanged.
const dispatchToastMock = vi.fn();
vi.mock("@fluentui/react-components", async () => {
  const actual =
    await vi.importActual<typeof import("@fluentui/react-components")>(
      "@fluentui/react-components",
    );
  return {
    ...actual,
    useToastController: () => ({
      dispatchToast: dispatchToastMock,
      dismissToast: vi.fn(),
      dismissAllToasts: vi.fn(),
      updateToast: vi.fn(),
      pauseToast: vi.fn(),
      playToast: vi.fn(),
    }),
  };
});

beforeEach(() => {
  dispatchToastMock.mockClear();
});

const m1: ChatMessage = { id: "1", role: "user", content: "hello" };
const m2: ChatMessage = { id: "2", role: "assistant", content: "hi back" };
const mWithReasoning: ChatMessage = {
  id: "3",
  role: "assistant",
  content: "answer body",
  reasoning: ["thinking step 1", "thinking step 2"],
};
const mWithError: ChatMessage = {
  id: "4",
  role: "assistant",
  content: "",
  error: "stream blew up",
};
const mWithEmptyReasoning: ChatMessage = {
  id: "5",
  role: "assistant",
  content: "no reasoning here",
  reasoning: [],
};

function Seed({ messages }: { messages: ChatMessage[] }) {
  const { dispatch } = useChat();
  (Seed as unknown as { _dispatch?: typeof dispatch })._dispatch = dispatch;
  void messages;
  return null;
}

describe("MessageList", () => {
  it("shows empty state when no messages", () => {
    render(
      <ChatProvider>
        <MessageList />
      </ChatProvider>,
    );
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("message-list")).toBeNull();
  });

  it("renders one <li> per message in dispatch order", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m1 });
      dispatch({ type: "add", message: m2 });
    });

    const list = screen.getByTestId("message-list");
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0]!.textContent).toContain("hello");
    expect(items[1]!.textContent).toContain("hi back");
  });

  it("tags each <li> with its role for styling hooks", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m1 });
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.getByTestId("message-1").getAttribute("data-role")).toBe("user");
    expect(screen.getByTestId("message-2").getAttribute("data-role")).toBe(
      "assistant",
    );
  });

  it("renders a collapsed reasoning <details> panel when reasoning entries exist on a finished message", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithReasoning });
    });

    const details = screen.getByTestId("message-3-reasoning");
    expect(details.tagName.toLowerCase()).toBe("details");
    expect((details as HTMLDetailsElement).open).toBe(false);
    const summary = details.querySelector("summary");
    expect(summary?.textContent).toBe("\u25B8 Thought process");
    expect(summary?.getAttribute("data-streaming")).toBe("false");
  });

  it("concatenates reasoning chunks into a single body block", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithReasoning });
    });

    const details = screen.getByTestId("message-3-reasoning");
    // Per-token deltas are joined verbatim (foundry_iq emits per-delta
    // chunks; concatenation reconstitutes the streamed text).
    expect(details.textContent).toContain("thinking step 1thinking step 2");
    expect(details.querySelectorAll("li")).toHaveLength(0);
  });

  it("drops model section titles and breaks reasoning blocks apart in the panel", () => {
    const mHeadered: ChatMessage = {
      id: "8",
      role: "assistant",
      content: "answer body",
      reasoning: [
        "**Searching for employee benefits**\n\nI will look it up.",
        "**Summarizing health benefits**\n\nHere is the summary.",
      ],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mHeadered });
    });

    const details = screen.getByTestId("message-8-reasoning");
    // The model's bold section titles are stripped from the panel...
    expect(details.textContent).not.toContain("Searching for employee benefits");
    expect(details.textContent).not.toContain("Summarizing health benefits");
    // ...and the remaining bodies render separated by a blank-line break.
    expect(details.textContent).toContain(
      "I will look it up.\n\nHere is the summary.",
    );
  });

  it("opens the reasoning panel and shows 'Thinking' while the message is streaming", () => {
    const mStreamingNoChunks: ChatMessage = {
      id: "6",
      role: "assistant",
      content: "",
      reasoning: [],
      streaming: true,
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mStreamingNoChunks });
    });

    const details = screen.getByTestId("message-6-reasoning");
    expect((details as HTMLDetailsElement).open).toBe(true);
    const summary = details.querySelector("summary");
    expect(summary?.textContent).toContain("Thinking");
    expect(summary?.getAttribute("data-streaming")).toBe("true");
  });

  it("streams joined reasoning chunks live while the message is still streaming", () => {
    const mStreamingWithChunks: ChatMessage = {
      id: "7",
      role: "assistant",
      content: "",
      reasoning: ["delta1", "delta2"],
      streaming: true,
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mStreamingWithChunks });
    });

    const details = screen.getByTestId("message-7-reasoning");
    expect((details as HTMLDetailsElement).open).toBe(true);
    expect(details.textContent).toContain("delta1delta2");
  });

  it("does not render a reasoning panel when reasoning is absent", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.queryByTestId("message-2-reasoning")).toBeNull();
  });

  it("does not render a reasoning panel when reasoning is an empty array", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithEmptyReasoning });
    });

    expect(screen.queryByTestId("message-5-reasoning")).toBeNull();
  });

  it("shows the reasoning placeholder when there are no reasoning frames yet", () => {
    const mPlaceholderOnly: ChatMessage = {
      id: "ph",
      role: "assistant",
      content: "",
      reasoning: [],
      reasoningPlaceholder:
        "Searching the knowledge base for relevant sources\u2026",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mPlaceholderOnly });
    });

    const details = screen.getByTestId("message-ph-reasoning");
    expect(details.textContent).toContain(
      "Searching the knowledge base for relevant sources\u2026",
    );
  });

  it("drops the placeholder once real reasoning frames arrive", () => {
    const mReasoningOverPlaceholder: ChatMessage = {
      id: "both",
      role: "assistant",
      content: "answer body",
      reasoning: ["real step"],
      reasoningPlaceholder:
        "Searching the knowledge base for relevant sources\u2026",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mReasoningOverPlaceholder });
    });

    const details = screen.getByTestId("message-both-reasoning");
    expect(details.textContent).toContain("real step");
    expect(details.textContent).not.toContain(
      "Searching the knowledge base for relevant sources\u2026",
    );
  });

  it("renders the reasoning panel and citation panel inside the same row as the avatar", () => {
    // Avatar-beside-Thinking layout (BUG-0012 refinement). For an
    // assistant message the avatar and the content column — the reasoning
    // <details>, the answer bubble, and the <CitationPanel> — share one
    // .row, so the avatar sits on the SAME horizontal line as the
    // "Thinking" panel instead of stacked above it. jsdom does not
    // evaluate the stylesheet (vitest css:false), so the executable
    // contract is the shared .row ancestor: the reasoning and citation
    // panels are no longer direct <li> children, and both live under the
    // row that also holds the avatar.
    const mReasoningAndCitations: ChatMessage = {
      id: "align",
      role: "assistant",
      content: "answer body",
      reasoning: ["why"],
      citations: [
        {
          id: "doc-z",
          title: "Doc Z",
          url: "https://example.com/z",
          snippet: "snippet",
          score: 0.5,
          metadata: {},
        },
      ],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mReasoningAndCitations });
    });

    const li = screen.getByTestId("message-align");
    const reasoning = screen.getByTestId("message-align-reasoning");
    const citationPanel = screen.getByTestId("citation-panel-align");
    const avatar = li.querySelector<HTMLElement>('span[data-role="assistant"]');
    expect(avatar).not.toBeNull();
    const row = avatar?.parentElement ?? null;
    expect(row).not.toBeNull();
    // The row is a direct child of the <li>, and holds the avatar plus
    // the reasoning + citation panels (one horizontal line).
    expect(row?.parentElement).toBe(li);
    expect(row?.contains(reasoning)).toBe(true);
    expect(row?.contains(citationPanel)).toBe(true);
    // The panels are no longer hung directly off the <li>.
    expect(reasoning.parentElement).not.toBe(li);
    expect(citationPanel.parentElement).not.toBe(li);
  });

  it("dispatches a Fluent error toast when message.error is set, and renders no inline alert", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithError });
    });

    expect(dispatchToastMock).toHaveBeenCalledTimes(1);
    const [toastNode, options] = dispatchToastMock.mock.calls[0] as [
      React.ReactElement,
      { intent?: string },
    ];
    expect(options.intent).toBe("error");
    // The toast content carries the raw error message somewhere in
    // its rendered subtree; we don't pin the exact element shape so
    // future copy / icon tweaks don't break the wiring test.
    const probe = render(toastNode);
    expect(probe.getByText("stream blew up")).toBeInTheDocument();
    probe.unmount();

    // The inline <p role="alert"> is gone — surfaced via toast only.
    expect(screen.queryByTestId("message-4-error")).toBeNull();
  });

  it("does not dispatch a toast when message.error is unset", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(dispatchToastMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("message-2-error")).toBeNull();
  });

  it("deduplicates toast dispatch for the same (id, error) across re-renders", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: unknown) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: mWithError });
    });
    expect(dispatchToastMock).toHaveBeenCalledTimes(1);

    // Re-dispatching the same set_error payload (e.g. a second
    // identical SSE error frame) must not re-toast.
    act(() => {
      dispatch({ type: "set_error", id: "4", error: "stream blew up" });
    });
    expect(dispatchToastMock).toHaveBeenCalledTimes(1);

    // A different error string for the same id IS a new failure and
    // must surface a fresh toast.
    act(() => {
      dispatch({ type: "set_error", id: "4", error: "second failure" });
    });
    expect(dispatchToastMock).toHaveBeenCalledTimes(2);
  });

  it("does not render any feedback controls under a finished assistant message", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = (Seed as unknown as { _dispatch: (a: { type: "add"; message: ChatMessage }) => void })._dispatch;

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.queryByTestId("feedback-2")).toBeNull();
    expect(screen.queryByTestId("feedback-2-positive")).toBeNull();
    expect(screen.queryByTestId("feedback-2-negative")).toBeNull();
  });
});

describe("MessageList citation rendering", () => {
  const cit1 = {
    id: "doc-x",
    title: "Doc X",
    url: "https://example.com/x",
    snippet: "Snippet body for doc x.",
    score: 0.5,
    metadata: {},
  };
  const cit2 = {
    id: "doc-y",
    title: "Doc Y",
    url: "https://example.com/y",
    snippet: "Snippet body for doc y.",
    score: null,
    metadata: {},
  };

  function getDispatch(): (action: {
    type: "add";
    message: ChatMessage;
  }) => void {
    return (
      Seed as unknown as {
        _dispatch: (a: { type: "add"; message: ChatMessage }) => void;
      }
    )._dispatch;
  }

  it("renders <CitationPanel> for a finished assistant message with citations", () => {
    const mWithCitations: ChatMessage = {
      id: "c-msg",
      role: "assistant",
      content: "answer",
      citations: [cit1, cit2],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mWithCitations });
    });

    expect(screen.getByTestId("citation-panel-c-msg")).toBeInTheDocument();
    expect(screen.getByTestId("citation-c-msg-doc-x")).toBeInTheDocument();
    expect(screen.getByTestId("citation-c-msg-doc-y")).toBeInTheDocument();
  });

  it("does NOT render <CitationPanel> while the assistant message is still streaming", () => {
    const mStreamingWithCitations: ChatMessage = {
      id: "c-stream",
      role: "assistant",
      content: "",
      streaming: true,
      citations: [cit1],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mStreamingWithCitations });
    });

    expect(screen.queryByTestId("citation-panel-c-stream")).toBeNull();
  });

  it("does NOT render <CitationPanel> when the citations array is empty", () => {
    const mEmptyCitations: ChatMessage = {
      id: "c-empty",
      role: "assistant",
      content: "answer",
      citations: [],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mEmptyCitations });
    });

    expect(screen.queryByTestId("citation-panel-c-empty")).toBeNull();
  });

  it("does NOT render <CitationPanel> for user messages even when citations are populated", () => {
    const mUserWithCitations: ChatMessage = {
      id: "c-user",
      role: "user",
      content: "question",
      citations: [cit1],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mUserWithCitations });
    });

    expect(screen.queryByTestId("citation-panel-c-user")).toBeNull();
  });
});

describe("MessageList answer-token rendering", () => {
  const cit1 = {
    id: "doc-alpha",
    title: "Alpha",
    url: "https://example.com/alpha",
    snippet: "alpha snippet",
    score: 0.5,
    metadata: {},
  };
  const cit2 = {
    id: "doc-beta",
    title: "Beta",
    url: "https://example.com/beta",
    snippet: "beta snippet",
    score: null,
    metadata: {},
  };

  function getDispatch(): (action: {
    type: "add";
    message: ChatMessage;
  }) => void {
    return (
      Seed as unknown as {
        _dispatch: (a: { type: "add"; message: ChatMessage }) => void;
      }
    )._dispatch;
  }

  it("renders inline [docN] tokens as clickable buttons in the assistant bubble", () => {
    const mWithTokens: ChatMessage = {
      id: "tok-1",
      role: "assistant",
      content: "see [doc1] and [doc2]",
      citations: [cit1, cit2],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mWithTokens });
    });

    expect(screen.getByTestId("answer-token-tok-1-1")).toBeInTheDocument();
    expect(screen.getByTestId("answer-token-tok-1-2")).toBeInTheDocument();
  });

  it("does NOT tokenize user message content", () => {
    const mUser: ChatMessage = {
      id: "tok-user",
      role: "user",
      content: "hey, what about [doc1]?",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mUser });
    });

    expect(screen.queryByTestId("answer-token-tok-user-1")).toBeNull();
    expect(screen.getByTestId("message-tok-user").textContent).toContain(
      "[doc1]",
    );
  });

  it("renders [docN] verbatim when the assistant message has no citations", () => {
    const mBare: ChatMessage = {
      id: "tok-bare",
      role: "assistant",
      content: "see [doc1] but no sources",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mBare });
    });

    expect(screen.queryByTestId("answer-token-tok-bare-1")).toBeNull();
    expect(screen.getByTestId("message-tok-bare").textContent).toContain(
      "[doc1]",
    );
  });

  it("clicking a [docN] token auto-expands the matching CitationPanel item", () => {
    const mLive: ChatMessage = {
      id: "tok-live",
      role: "assistant",
      content: "see [doc2] for details",
      citations: [cit1, cit2],
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    act(() => {
      getDispatch()({ type: "add", message: mLive });
    });

    const headerB = screen
      .getByTestId("citation-tok-live-doc-beta-header")
      .querySelector("button")!;
    expect(headerB.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(screen.getByTestId("answer-token-tok-live-2"));

    expect(headerB.getAttribute("aria-expanded")).toBe("true");
  });
});

describe("MessageList auto scroll-to-bottom", () => {
  let scrollSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    scrollSpy = vi
      .spyOn(HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    scrollSpy.mockRestore();
  });

  function getDispatch(): (
    action:
      | { type: "add"; message: ChatMessage }
      | { type: "append_answer"; id: string; chunk: string },
  ) => void {
    return (
      Seed as unknown as {
        _dispatch: (
          a:
            | { type: "add"; message: ChatMessage }
            | { type: "append_answer"; id: string; chunk: string },
        ) => void;
      }
    )._dispatch;
  }

  it("renders a bottom sentinel inside the message list", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({ type: "add", message: m1 });
    });
    expect(
      screen.getByTestId("message-list-bottom"),
    ).toBeInTheDocument();
  });

  it("scrolls the bottom sentinel into view when a new message is added", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    scrollSpy.mockClear();
    act(() => {
      dispatch({ type: "add", message: m1 });
    });
    expect(scrollSpy).toHaveBeenCalled();
    const [scrolledEl] = scrollSpy.mock.contexts;
    expect(
      (scrolledEl as HTMLElement).getAttribute("data-testid"),
    ).toBe("message-list-bottom");
  });

  it("scrolls the bottom sentinel into view as streaming content grows", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({
        type: "add",
        message: {
          id: "live",
          role: "assistant",
          content: "",
          streaming: true,
        },
      });
    });
    scrollSpy.mockClear();
    act(() => {
      dispatch({ type: "append_answer", id: "live", chunk: "hello " });
    });
    expect(scrollSpy).toHaveBeenCalled();
    scrollSpy.mockClear();
    act(() => {
      dispatch({ type: "append_answer", id: "live", chunk: "world" });
    });
    expect(scrollSpy).toHaveBeenCalled();
  });

  it("does not call scrollIntoView when the transcript is empty", () => {
    render(
      <ChatProvider>
        <MessageList />
      </ChatProvider>,
    );
    expect(scrollSpy).not.toHaveBeenCalled();
  });
});
