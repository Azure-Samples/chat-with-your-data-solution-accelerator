/**
 * Pillar: Stable Core
 * Phase: 1
 */
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "@/App";
import { resetRuntimeConfig } from "@/api/runtimeConfig";

describe("App", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    resetRuntimeConfig();
    vi.restoreAllMocks();
  });

  it("renders the placeholder heading", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { level: 1, name: /CWYD v2/i }),
    ).toBeInTheDocument();
  });

  it("reports backend health when /api/health resolves", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("health")).toHaveTextContent(
        /connected to backend/i,
      );
    });
  });

  it("surfaces a non-2xx health response as an error", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response("nope", { status: 503 }),
    ) as typeof fetch;
    render(<App />);
    await waitFor(() => {
      // Scope to the health element -- the history panel also renders
      // an alert when its own /api/history calls fail.
      expect(screen.getByTestId("health")).toHaveTextContent(/HTTP 503/);
    });
  });

  it("loads /config at boot and targets the resolved backend for health", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/config") {
        return new Response(
          JSON.stringify({ backendUrl: "https://backend.example.com" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    globalThis.fetch = fetchMock as typeof fetch;

    render(<App />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "https://backend.example.com/api/health",
        expect.anything(),
      );
    });
  });
});
