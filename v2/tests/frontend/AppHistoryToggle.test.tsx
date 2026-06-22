/**
 * Pillar: Stable Core
 * Phase: 6 (frontend polish, pulled forward for boss demo)
 *
 * Tests for the history-toggle wiring at the App level: the AppHeader
 * history button must drive ChatPage's `data-history-open` attribute,
 * and the sidebar must default to collapsed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "@/App";

beforeEach(() => {
  // Stub the entire fetch surface (health + history endpoints) so the
  // App tree resolves without relying on a real backend.
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
      }
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
  document.documentElement.removeAttribute("data-theme");
  window.localStorage.clear();
});

function getChatPage(): HTMLElement {
  return screen.getByTestId("chat-page");
}

function getHistoryButton(): HTMLElement {
  return screen.getByRole("button", { name: /history/i });
}

describe("App history toggle wiring", () => {
  it("renders the chat shell with the history sidebar collapsed by default", async () => {
    render(<App />);
    await waitFor(() => {
      expect(getChatPage()).toHaveAttribute("data-history-open", "false");
    });
    expect(getHistoryButton()).toHaveAttribute("aria-pressed", "false");
  });

  it("opens the history sidebar when the header history button is clicked", async () => {
    render(<App />);
    await waitFor(() => {
      expect(getChatPage()).toBeInTheDocument();
    });
    fireEvent.click(getHistoryButton());
    expect(getChatPage()).toHaveAttribute("data-history-open", "true");
    expect(getHistoryButton()).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles back to collapsed on a second click", async () => {
    render(<App />);
    await waitFor(() => {
      expect(getChatPage()).toBeInTheDocument();
    });
    fireEvent.click(getHistoryButton());
    fireEvent.click(getHistoryButton());
    expect(getChatPage()).toHaveAttribute("data-history-open", "false");
    expect(getHistoryButton()).toHaveAttribute("aria-pressed", "false");
  });
});
