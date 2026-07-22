import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatPage } from "@/pages/chat/ChatPage";
import { streamChat } from "@/api/streamChat";
import { fetchConversation } from "@/api/conversationHistory";
import type {
  ChatMessage,
  HistoryConversation,
  StreamEvent,
} from "@/models/chat";

// `MessageInput` calls `streamChat` on submit.
// Stub the module so the integration assertions stay focused on the
// shell wiring rather than the SSE wire format (covered in the unit
// tests for `streamChat` + `MessageInput`).
vi.mock("@/api/streamChat", () => ({
  streamChat: vi.fn(),
}));
const streamChatMock = vi.mocked(streamChat);

// `ChatShell` calls `fetchConversation` when a history row is selected.
// Stub it so the selection tests assert the dispatch -> transcript
// rehydration without exercising the real fetch + map (covered in the
// `fetchConversation` unit tests).
vi.mock("@/api/conversationHistory", () => ({
  fetchConversation: vi.fn(),
}));
const fetchConversationMock = vi.mocked(fetchConversation);

function emptyStream(): AsyncIterable<StreamEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      // no events
    },
  };
}

// A stream that yields one answer frame + one citation frame, so the
// assistant message lands with a renderable reference chip. Used to
// exercise the right-hand citation detail column wiring.
function citationStream(): AsyncIterable<StreamEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      yield { channel: "answer", content: "Here is the answer.", metadata: {} };
      yield {
        channel: "citation",
        content: "",
        metadata: {
          id: "doc-1",
          title: "Benefit Options",
          url: "https://example.com/benefit-options.pdf",
          snippet: "**Health** coverage details.",
          score: null,
          metadata: {},
        },
      };
    },
  };
}

// A stream that yields one answer frame and then mints a brand-new
// conversation id via `onConversationId` -- modelling the backend's
// terminal control frame at the end of a freshly-persisted turn.
function newConversationStream(
  conversationId: string,
  onConversationId?: (id: string) => void,
): AsyncIterable<StreamEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      yield { channel: "answer", content: "Answer.", metadata: {} };
      onConversationId?.(conversationId);
    },
  };
}

async function openCitationDetail() {
  fireEvent.change(screen.getByLabelText(/message/i), {
    target: { value: "hi" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  const toggle = await screen.findByRole("button", { name: /1 reference/i });
  fireEvent.click(toggle);
  fireEvent.click(screen.getByRole("button", { name: /Benefit Options/i }));
}

// HistoryPanel calls /api/history on mount. Stub fetch
// so the panel resolves to "no conversations" and the existing
// chat-shell assertions stay focused on the input/list wiring.
beforeEach(() => {
  streamChatMock.mockReturnValue(emptyStream());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/history/status")) {
        return new Response(
          JSON.stringify({ enabled: true, db_type: "cosmosdb" }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/history/conversations")) {
        return new Response("[]", { status: 200 });
      }
      return new Response("not found", { status: 404 });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  streamChatMock.mockReset();
  fetchConversationMock.mockReset();
});

describe("ChatPage", () => {
  it("renders the chat heading and empty state", () => {
    render(<ChatPage />);
    expect(screen.getByRole("heading", { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
  });

  it("wires the input dispatch into the list", async () => {
    render(<ChatPage />);
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "ping" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    // Submit dispatches the user msg + an assistant placeholder; both
    // render as <li> children in the message list.
    await waitFor(() => {
      const list = screen.getByTestId("message-list");
      expect(list.querySelectorAll("li")).toHaveLength(2);
      expect(list.textContent).toContain("ping");
    });
    expect(streamChatMock).toHaveBeenCalledTimes(1);
  });

  it("provides its own ChatContext (no shared global state)", async () => {
    const first = render(<ChatPage />);
    fireEvent.change(first.getByLabelText(/message/i), {
      target: { value: "alpha" },
    });
    fireEvent.click(first.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(first.getByTestId("message-list")).toBeInTheDocument();
    });
    first.unmount();

    render(<ChatPage />);
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
  });

  it("keeps the citation detail column closed until a chip is clicked", () => {
    streamChatMock.mockReturnValue(emptyStream());
    render(<ChatPage />);
    expect(screen.getByTestId("chat-page").getAttribute("data-citation-open")).toBe(
      "false",
    );
    expect(screen.queryByTestId("citation-detail-panel")).toBeNull();
  });

  it("opens the citation detail column when a reference chip is clicked", async () => {
    streamChatMock.mockReturnValue(citationStream());
    render(<ChatPage />);
    const page = screen.getByTestId("chat-page");

    await openCitationDetail();

    expect(page.getAttribute("data-citation-open")).toBe("true");
    expect(screen.getByTestId("citation-detail-panel")).toBeInTheDocument();
    expect(screen.getByTestId("citation-detail-title")).toHaveTextContent(
      "Benefit Options",
    );
    // Push, not overlay: the transcript stays mounted alongside the panel.
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  it("closes the citation detail column from the dismiss control", async () => {
    streamChatMock.mockReturnValue(citationStream());
    render(<ChatPage />);
    const page = screen.getByTestId("chat-page");

    await openCitationDetail();
    expect(page.getAttribute("data-citation-open")).toBe("true");

    fireEvent.click(screen.getByTestId("citation-detail-dismiss"));

    expect(page.getAttribute("data-citation-open")).toBe("false");
    expect(screen.queryByTestId("citation-detail-panel")).toBeNull();
  });
});

function stubHistoryList(conversations: HistoryConversation[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/history/status")) {
        return new Response(
          JSON.stringify({ enabled: true, db_type: "cosmosdb" }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/history/conversations")) {
        return new Response(JSON.stringify(conversations), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    }),
  );
}

describe("ChatPage history selection", () => {
  const priorConversation: HistoryConversation = {
    id: "conv-7",
    title: "Prior chat",
    updated_at: "2026-06-15T00:00:00Z",
  };

  it("loads the selected conversation into the transcript with its citations", async () => {
    stubHistoryList([priorConversation]);
    const messages: ChatMessage[] = [
      { id: "m1", role: "user", content: "earlier question" },
      {
        id: "m2",
        role: "assistant",
        content: "earlier answer",
        citations: [
          {
            id: "src-1",
            title: "Doc One",
            url: "",
            snippet: "a snippet",
            score: 0.9,
            metadata: {},
          },
        ],
      },
    ];
    fetchConversationMock.mockResolvedValue({
      conversationId: "conv-7",
      messages,
    });

    render(<ChatPage historyOpen />);
    fireEvent.click(await screen.findByTestId("history-select-conv-7"));

    await waitFor(() => {
      const list = screen.getByTestId("message-list");
      expect(list.querySelectorAll("li")).toHaveLength(2);
      expect(list.textContent).toContain("earlier question");
      expect(list.textContent).toContain("earlier answer");
    });
    expect(fetchConversationMock).toHaveBeenCalledWith("conv-7");
    // The rehydrated assistant turn keeps its persisted citation chip.
    expect(
      screen.getByRole("button", { name: /1 reference/i }),
    ).toBeInTheDocument();
  });

  it("marks the selected history row current on click", async () => {
    stubHistoryList([priorConversation]);
    fetchConversationMock.mockResolvedValue({
      conversationId: "conv-7",
      messages: [{ id: "m1", role: "user", content: "earlier question" }],
    });

    render(<ChatPage historyOpen />);
    fireEvent.click(await screen.findByTestId("history-select-conv-7"));

    await waitFor(() => {
      expect(screen.getByTestId("message-list").textContent).toContain(
        "earlier question",
      );
    });
    expect(
      screen.getByTestId("history-item-conv-7").getAttribute("aria-current"),
    ).toBe("true");
  });

  it("keeps the live transcript when the conversation load fails", async () => {
    stubHistoryList([priorConversation]);
    fetchConversationMock.mockRejectedValue(new Error("HTTP 404"));

    render(<ChatPage historyOpen />);
    // Seed a live transcript via a normal submit (empty SSE stream ->
    // user message + assistant placeholder).
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "live question" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(
        screen.getByTestId("message-list").querySelectorAll("li"),
      ).toHaveLength(2);
    });

    fireEvent.click(await screen.findByTestId("history-select-conv-7"));
    await waitFor(() => {
      expect(fetchConversationMock).toHaveBeenCalledWith("conv-7");
    });

    // Failed load: the transcript is untouched and the row stays current.
    const list = screen.getByTestId("message-list");
    expect(list.querySelectorAll("li")).toHaveLength(2);
    expect(list.textContent).toContain("live question");
    expect(
      screen.getByTestId("history-item-conv-7").getAttribute("aria-current"),
    ).toBe("true");
  });
});

describe("ChatPage history auto-refresh", () => {
  function stubCountingHistory(): { count: () => number } {
    let historyListCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.endsWith("/api/history/status")) {
          return new Response(
            JSON.stringify({ enabled: true, db_type: "cosmosdb" }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/history/conversations")) {
          historyListCalls += 1;
          return new Response("[]", { status: 200 });
        }
        return new Response("not found", { status: 404 });
      }),
    );
    return { count: () => historyListCalls };
  }

  it("refetches the conversation history after a new conversation is inserted", async () => {
    const history = stubCountingHistory();
    streamChatMock.mockImplementation((_messages, options) =>
      newConversationStream("conv-new", options?.onConversationId),
    );

    render(<ChatPage historyOpen />);

    // History loads once on mount.
    await waitFor(() => {
      expect(history.count()).toBe(1);
    });

    // The first message in a fresh chat mints a conversation id,
    // flipping conversationId null -> non-null; the panel silently
    // re-fetches so the new entry appears.
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "first message" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(history.count()).toBe(2);
    });
  });

  it("does not refetch history while the same conversation continues", async () => {
    const history = stubCountingHistory();
    streamChatMock.mockImplementation((_messages, options) =>
      newConversationStream("conv-stable", options?.onConversationId),
    );

    render(<ChatPage historyOpen />);
    await waitFor(() => {
      expect(history.count()).toBe(1);
    });

    // First message mints conv-stable -> one refetch (count 2).
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "first" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(history.count()).toBe(2);
    });

    // Second message re-emits the SAME id; conversationId does not
    // transition null -> non-null, so no further refetch fires.
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "second" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledTimes(2);
    });
    // Flush any pending effects, then confirm no extra history call.
    await Promise.resolve();
    await Promise.resolve();
    expect(history.count()).toBe(2);
  });
});
