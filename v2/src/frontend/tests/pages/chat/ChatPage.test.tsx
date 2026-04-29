import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatPage } from "../../../src/pages/chat/ChatPage";

// HistoryPanel (dev_plan #32) calls /api/history on mount. Stub fetch
// so the panel resolves to "no conversations" and the existing
// chat-shell assertions stay focused on the input/list wiring.
beforeEach(() => {
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
});

describe("ChatPage", () => {
  it("renders the chat heading and empty state", () => {
    render(<ChatPage />);
    expect(screen.getByRole("heading", { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
  });

  it("wires the input dispatch into the list", () => {
    render(<ChatPage />);
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "ping" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    const list = screen.getByTestId("message-list");
    expect(list.querySelectorAll("li")).toHaveLength(1);
    expect(list.textContent).toContain("ping");
  });

  it("provides its own ChatContext (no shared global state)", () => {
    const first = render(<ChatPage />);
    fireEvent.change(first.getByLabelText(/message/i), {
      target: { value: "alpha" },
    });
    fireEvent.click(first.getByRole("button", { name: /send/i }));
    first.unmount();

    render(<ChatPage />);
    expect(screen.getByTestId("message-list-empty")).toBeInTheDocument();
  });
});
