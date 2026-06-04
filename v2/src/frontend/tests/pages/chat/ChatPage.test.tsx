import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatPage } from "@/pages/chat/ChatPage";
import { streamChat } from "@/api/streamChat";
import type { StreamEvent } from "@/models/chat";

// `MessageInput` calls `streamChat` on submit (dev_plan #24, C2b).
// Stub the module so the integration assertions stay focused on the
// shell wiring rather than the SSE wire format (covered in the unit
// tests for `streamChat` + `MessageInput`).
vi.mock("../../../src/api/streamChat", () => ({
  streamChat: vi.fn(),
}));
const streamChatMock = vi.mocked(streamChat);

function emptyStream(): AsyncIterable<StreamEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      // no events
    },
  };
}

// HistoryPanel (dev_plan #32) calls /api/history on mount. Stub fetch
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
});
