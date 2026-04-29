/**
 * Pillar: Stable Core
 * Phase: 1
 */
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

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
});
