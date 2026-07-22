/**
 * App-level navigation tests: the header's gated admin entry must
 * appear only on a successful `getAdminStatus()` probe, the App must
 * route into the admin layout when that entry is clicked, and admin
 * URLs must deep-link / redirect correctly. The header no longer
 * renders a primary admin nav -- admin is reached solely via the gated
 * entry. The app header renders only on the chat route -- admin routes
 * hide it so the AdminLayout chrome owns the admin frame.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { App } from "@/App";

interface FetchStubOptions {
  adminOk: boolean;
}

const ADMIN_STATUS_FIXTURE = {
  orchestrator_name: "langgraph",
  db_type: "cosmosdb",
  index_store: "azure_search",
  environment: "local",
  foundry_project_endpoint_host: "fdy-abc123.services.ai.azure.com",
  gpt_deployment: "gpt-5",
  embedding_deployment: "text-embedding-3-large",
  search_enabled: true,
  app_insights_enabled: false,
  cors_origins: [] as string[],
  version: "2.0.0",
};

const ADMIN_CONFIG_FIXTURE = {
  orchestrator_name: "langgraph",
  openai_temperature: 0.0,
  openai_max_tokens: 4096,
  search_use_semantic_search: true,
  search_top_k: 5,
  log_level: "INFO",
  content_safety_enabled: false,
  cwyd_agent_instructions: "You are the Chat With Your Data assistant.",
};

function stubFetch({ adminOk }: FetchStubOptions): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/health")) {
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/api/admin/status")) {
        if (adminOk) {
          return new Response(JSON.stringify(ADMIN_STATUS_FIXTURE), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("forbidden", { status: 403 });
      }
      if (url.endsWith("/api/admin/documents")) {
        return new Response(
          JSON.stringify({ documents: [], total: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/admin/config")) {
        return new Response(JSON.stringify(ADMIN_CONFIG_FIXTURE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/api/history/status")) {
        return new Response(
          JSON.stringify({ enabled: false, db_type: "none" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/history/conversations")) {
        return new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    }),
  );
}

/**
 * Admin routes hide the app header, so there's no probe-gated element
 * to await on. Flush the in-flight `getAdminStatus()` probe inside
 * act() so its state update lands before teardown.
 */
async function flushAdminProbe(): Promise<void> {
  await act(async () => {
    // Drain the pending admin-status promise + its setState.
  });
}

beforeEach(() => {
  // Each test sets its own admin posture via stubFetch().
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-theme");
  window.localStorage.clear();
});

describe("App navigation", () => {
  it("hides the Admin entry when /api/admin/status returns 403", async () => {
    stubFetch({ adminOk: false });
    render(<App />);
    // Chat renders immediately; once the probe settles to forbidden the
    // gated admin entry stays hidden.
    await waitFor(() => {
      expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
  });

  it("shows the Admin entry when /api/admin/status returns 200", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    expect(await screen.findByTestId("header-admin")).toBeInTheDocument();
  });

  it("does not render a primary admin nav in the header", async () => {
    // Regression guard: the four admin nav buttons that used to sit in
    // the header are gone; admin is reached only via the gated entry.
    stubFetch({ adminOk: true });
    render(<App />);
    await screen.findByTestId("header-admin");
    expect(screen.queryByTestId("primary-nav")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-ingest")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-delete")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-config")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-prompt")).not.toBeInTheDocument();
  });

  it("keeps the Admin entry hidden while the admin probe is in flight", () => {
    // Stub fetch with a never-resolving Admin probe so the tri-state
    // `adminAvailable === null` branch is exercised synchronously.
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.endsWith("/api/admin/status")) {
          return new Promise(() => {
            /* never resolves */
          });
        }
        if (url.endsWith("/api/health")) {
          return Promise.resolve(
            new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
          );
        }
        return Promise.resolve(new Response("[]", { status: 200 }));
      }),
    );
    render(<App />);
    expect(screen.getByTestId("app-header")).toBeInTheDocument();
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
  });

  it("deep-links straight to an admin page from its URL", async () => {
    window.history.pushState({}, "", "/admin/delete");
    stubFetch({ adminOk: true });
    render(<App />);

    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/admin/delete");
    expect(screen.queryByTestId("app-header")).not.toBeInTheDocument();
    await flushAdminProbe();
  });

  it("hides the app header on admin routes", async () => {
    window.history.pushState({}, "", "/admin/ingest");
    stubFetch({ adminOk: true });
    render(<App />);

    expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("app-header")).not.toBeInTheDocument();
    expect(screen.queryByTestId("header-admin")).not.toBeInTheDocument();
    await flushAdminProbe();
  });

  it("redirects an unknown route back to the chat root", async () => {
    window.history.pushState({}, "", "/does/not/exist");
    stubFetch({ adminOk: true });
    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
    });
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  it("opens the admin section via the header admin button", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const adminButton = await screen.findByTestId("header-admin");

    fireEvent.click(adminButton);

    expect(window.location.pathname).toBe("/admin/ingest");
    expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
  });

  it("renders admin pages inside the admin layout shell", async () => {
    window.history.pushState({}, "", "/admin/delete");
    stubFetch({ adminOk: true });
    render(<App />);

    expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
    expect(screen.getByTestId("admin-subnav")).toBeInTheDocument();
    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    await flushAdminProbe();
  });

  it("redirects bare /admin to the ingest page", async () => {
    window.history.pushState({}, "", "/admin");
    stubFetch({ adminOk: true });
    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/admin/ingest");
    });
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    await flushAdminProbe();
  });

  it("returns to chat when the admin back-home button is clicked", async () => {
    window.history.pushState({}, "", "/admin/ingest");
    stubFetch({ adminOk: true });
    render(<App />);
    const backHome = await screen.findByTestId("admin-back-home");

    fireEvent.click(backHome);

    expect(window.location.pathname).toBe("/");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("admin-layout")).not.toBeInTheDocument();
  });
});
