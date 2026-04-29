/**
 * Pillar: Scenario Pack / Phase: 4 (task #32) -- HistoryPanel tests.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { HistoryPanel } from "../../../../src/pages/chat/components/HistoryPanel";

interface FakeConv {
  id: string;
  title: string;
  updated_at: string;
}

interface RouteHandlers {
  status?: () => Response | Promise<Response>;
  list?: () => Response | Promise<Response>;
  create?: (body: unknown) => Response | Promise<Response>;
  rename?: (id: string, body: unknown) => Response | Promise<Response>;
  remove?: (id: string) => Response | Promise<Response>;
}

function installFetch(routes: RouteHandlers) {
  const calls: { url: string; method: string; body?: unknown }[] = [];
  const json = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const noContent = () => new Response(null, { status: 204 });

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      const body = init?.body
        ? JSON.parse(init.body as string)
        : undefined;
      calls.push({ url, method, body });

      if (url.endsWith("/api/history/status") && method === "GET") {
        return (
          routes.status?.() ?? json({ enabled: true, db_type: "cosmosdb" })
        );
      }
      if (url.endsWith("/api/history/conversations")) {
        if (method === "POST") {
          return (
            routes.create?.(body) ?? json({ id: "new-id", title: "New chat", updated_at: "t" }, 201)
          );
        }
        return routes.list?.() ?? json([]);
      }
      const match = url.match(/\/api\/history\/conversations\/([^/]+)$/);
      if (match) {
        const id = decodeURIComponent(match[1]);
        if (method === "PATCH") {
          return (
            routes.rename?.(id, body) ?? json({ id, title: (body as { title: string }).title, updated_at: "t" })
          );
        }
        if (method === "DELETE") {
          return routes.remove?.(id) ?? noContent();
        }
      }
      return new Response("not found", { status: 404 });
    }),
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const sampleList: FakeConv[] = [
  { id: "c-1", title: "First", updated_at: "2026-04-28T01:00:00Z" },
  { id: "c-2", title: "Second", updated_at: "2026-04-28T00:00:00Z" },
];

describe("HistoryPanel", () => {
  it("loads /api/history/status + /conversations on mount", async () => {
    const calls = installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });

    render(<HistoryPanel />);

    expect(await screen.findByTestId("history-list")).toBeInTheDocument();
    expect(screen.getByTestId("history-db-type")).toHaveTextContent("cosmosdb");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    const urls = calls.map((c) => c.url);
    expect(urls.some((u) => u.endsWith("/api/history/status"))).toBe(true);
    expect(urls.some((u) => u.endsWith("/api/history/conversations"))).toBe(true);
  });

  it("renders the empty state when the API returns no conversations", async () => {
    installFetch({});
    render(<HistoryPanel />);
    expect(await screen.findByTestId("history-empty")).toBeInTheDocument();
  });

  it("surfaces an error message when the list call fails", async () => {
    installFetch({
      list: () => new Response("server bork", { status: 500 }),
    });
    render(<HistoryPanel />);
    expect(await screen.findByTestId("history-error")).toHaveTextContent(
      "HTTP 500",
    );
  });

  it("invokes onSelect when a row is clicked", async () => {
    installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    const onSelect = vi.fn();
    render(<HistoryPanel onSelect={onSelect} />);

    const row = await screen.findByTestId("history-select-c-2");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith("c-2");
  });

  it("marks the selected row with aria-current", async () => {
    installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    render(<HistoryPanel selectedId="c-1" />);
    const item = await screen.findByTestId("history-item-c-1");
    expect(item).toHaveAttribute("aria-current", "true");
  });

  it("creates a new conversation, prepends it, and selects it", async () => {
    const calls = installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
      create: () =>
        new Response(
          JSON.stringify({
            id: "c-new",
            title: "New chat",
            updated_at: "2026-04-28T02:00:00Z",
          }),
          { status: 201 },
        ),
    });
    const onSelect = vi.fn();
    render(<HistoryPanel onSelect={onSelect} />);

    await screen.findByTestId("history-list");
    fireEvent.click(screen.getByTestId("history-new"));

    await waitFor(() => {
      expect(screen.getByTestId("history-item-c-new")).toBeInTheDocument();
    });
    expect(onSelect).toHaveBeenCalledWith("c-new");

    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ title: "New chat" });
  });

  it("renames a conversation when the prompt resolves to a non-empty value", async () => {
    installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    vi.spyOn(window, "prompt").mockReturnValue("Renamed");
    render(<HistoryPanel />);

    await screen.findByTestId("history-list");
    fireEvent.click(screen.getByTestId("history-rename-c-1"));

    await waitFor(() => {
      expect(screen.getByTestId("history-select-c-1")).toHaveTextContent(
        "Renamed",
      );
    });
  });

  it("skips the rename request when the user cancels the prompt", async () => {
    const calls = installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    vi.spyOn(window, "prompt").mockReturnValue(null);
    render(<HistoryPanel />);

    await screen.findByTestId("history-list");
    fireEvent.click(screen.getByTestId("history-rename-c-1"));

    // Give microtasks a beat; PATCH must never fire.
    await Promise.resolve();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("deletes a conversation after confirmation and removes it from the list", async () => {
    installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<HistoryPanel />);

    await screen.findByTestId("history-list");
    fireEvent.click(screen.getByTestId("history-delete-c-1"));

    await waitFor(() => {
      expect(screen.queryByTestId("history-item-c-1")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("history-item-c-2")).toBeInTheDocument();
  });

  it("skips the delete request when the user cancels the confirm", async () => {
    const calls = installFetch({
      list: () =>
        new Response(JSON.stringify(sampleList), { status: 200 }),
    });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<HistoryPanel />);

    await screen.findByTestId("history-list");
    fireEvent.click(screen.getByTestId("history-delete-c-1"));

    await Promise.resolve();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    expect(screen.getByTestId("history-item-c-1")).toBeInTheDocument();
  });
});
