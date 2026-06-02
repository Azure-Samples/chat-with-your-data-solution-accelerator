import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  ChatProvider,
  useChat,
  type ChatMessage,
} from "../../../../src/pages/chat/ChatContext";
import { MessageList } from "../../../../src/pages/chat/components/MessageList";

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
    expect(items[0].textContent).toContain("hello");
    expect(items[1].textContent).toContain("hi back");
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

  it("renders an inline error notice when message.error is set", () => {
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

    const notice = screen.getByTestId("message-4-error");
    expect(notice.getAttribute("role")).toBe("alert");
    expect(notice.textContent).toContain("stream blew up");
  });

  it("does not render an error notice when message.error is unset", () => {
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

    expect(screen.queryByTestId("message-2-error")).toBeNull();
  });
});

describe("MessageList feedback wiring", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function noContent(): Response {
    return new Response(null, { status: 204 });
  }

  function errorResponse(status: number): Response {
    return new Response(JSON.stringify({ detail: "nope" }), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

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

  it("renders FeedbackButtons under finished assistant messages", () => {
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();

    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    expect(screen.getByTestId("feedback-2")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-2-positive")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-2-negative")).toBeInTheDocument();
  });

  it("does NOT render FeedbackButtons for user messages", () => {
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

    expect(screen.queryByTestId("feedback-1")).toBeNull();
  });

  it("does NOT render FeedbackButtons while an assistant message is still streaming", () => {
    const mStreaming: ChatMessage = {
      id: "s1",
      role: "assistant",
      content: "",
      streaming: true,
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();

    act(() => {
      dispatch({ type: "add", message: mStreaming });
    });

    expect(screen.queryByTestId("feedback-s1")).toBeNull();
  });

  it("reflects an already-set feedback value as the pressed thumb", () => {
    const mWithPositive: ChatMessage = {
      id: "fp",
      role: "assistant",
      content: "answer",
      feedback: "positive",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();

    act(() => {
      dispatch({ type: "add", message: mWithPositive });
    });

    expect(screen.getByTestId("feedback-fp-positive")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("feedback-fp-negative")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("POSTs feedback and optimistically locks the thumb on 👍 click", async () => {
    fetchMock.mockResolvedValueOnce(noContent());

    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("feedback-2-positive"));
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/history/messages/2/feedback");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ feedback: "positive" }));

    await waitFor(() => {
      expect(screen.getByTestId("feedback-2-positive")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    });
  });

  it("rolls back the optimistic dispatch when the POST fails", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(500));

    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({ type: "add", message: m2 });
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("feedback-2-positive"));
    });

    // After rollback the thumb is unpressed again (initial state was undefined).
    await waitFor(() => {
      expect(screen.getByTestId("feedback-2-positive")).toHaveAttribute(
        "aria-pressed",
        "false",
      );
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rolls back to the previous feedback value (not null) when overwriting fails", async () => {
    const mAlreadyPositive: ChatMessage = {
      id: "fp",
      role: "assistant",
      content: "answer",
      feedback: "positive",
    };
    fetchMock.mockResolvedValueOnce(errorResponse(422));

    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({ type: "add", message: mAlreadyPositive });
    });

    // 👎 is currently unpressed; clicking it opens the reason form,
    // then submitting sends "negative".
    await act(async () => {
      fireEvent.click(screen.getByTestId("feedback-fp-negative"));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId("feedback-fp-reason-submit"));
    });

    // After the 422 rollback the original positive feedback is restored.
    await waitFor(() => {
      expect(screen.getByTestId("feedback-fp-positive")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    });
    expect(screen.getByTestId("feedback-fp-negative")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("URL-encodes the message id when POSTing feedback", async () => {
    fetchMock.mockResolvedValueOnce(noContent());

    const mFunky: ChatMessage = {
      id: "msg/with space",
      role: "assistant",
      content: "answer",
    };
    render(
      <ChatProvider>
        <Seed messages={[]} />
        <MessageList />
      </ChatProvider>,
    );
    const dispatch = getDispatch();
    act(() => {
      dispatch({ type: "add", message: mFunky });
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("feedback-msg/with space-positive"));
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe(
      "/api/history/messages/msg%2Fwith%20space/feedback",
    );
  });
});
