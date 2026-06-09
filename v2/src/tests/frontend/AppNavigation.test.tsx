/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * App-level navigation tests: the primary nav slot in the header must
 * gate the Admin button on a successful `getAdminStatus()` probe and
 * the App must swap between the chat view and the admin "Ingest data"
 * view based on the active nav selection.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "@/App";
import { Section } from "@/models/sections";

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
  reasoning_deployment: "gpt-5",
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

beforeEach(() => {
  // Each test sets its own admin posture via stubFetch().
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-theme");
  window.localStorage.clear();
});

describe("App primary navigation", () => {
  it("renders the primary nav with the Chat link visible by default", () => {
    stubFetch({ adminOk: true });
    render(<App />);
    expect(screen.getByTestId("primary-nav")).toBeInTheDocument();
    expect(screen.getByTestId("nav-chat")).toBeInTheDocument();
  });

  it("hides the Admin link when /api/admin/status returns 403", async () => {
    stubFetch({ adminOk: false });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("primary-nav")).toHaveAttribute(
        "data-admin-status",
        "forbidden",
      );
    });
    expect(screen.queryByTestId("nav-admin-ingest")).not.toBeInTheDocument();
  });

  it("shows the Admin link when /api/admin/status returns 200", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("primary-nav")).toHaveAttribute(
        "data-admin-status",
        "available",
      );
    });
    expect(screen.getByTestId("nav-admin-ingest")).toBeInTheDocument();
  });

  it("shows the Delete data link when /api/admin/status returns 200", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("nav-admin-delete")).toBeInTheDocument();
    });
  });

  it("hides the Delete data link when /api/admin/status returns 403", async () => {
    stubFetch({ adminOk: false });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("primary-nav")).toHaveAttribute(
        "data-admin-status",
        "forbidden",
      );
    });
    expect(screen.queryByTestId("nav-admin-delete")).not.toBeInTheDocument();
  });

  it("marks the Chat button as the current page on first render", () => {
    stubFetch({ adminOk: true });
    render(<App />);
    expect(screen.getByTestId("nav-chat")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("switches to the IngestData view when the Admin link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const adminLink = await screen.findByTestId("nav-admin-ingest");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();

    fireEvent.click(adminLink);

    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-admin-ingest")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId(`nav-${Section.Chat}`)).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("switches back to the chat view when the Chat link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const adminLink = await screen.findByTestId("nav-admin-ingest");
    fireEvent.click(adminLink);
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("nav-chat"));

    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.getByTestId(`nav-${Section.Chat}`)).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("switches to the DeleteData view when the Delete data link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const deleteLink = await screen.findByTestId("nav-admin-delete");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();

    fireEvent.click(deleteLink);

    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-admin-delete")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId(`nav-${Section.Chat}`)).not.toHaveAttribute(
      "aria-current",
    );
    expect(screen.getByTestId("nav-admin-ingest")).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("switches between the two admin views when their nav links are clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const ingestLink = await screen.findByTestId("nav-admin-ingest");
    const deleteLink = screen.getByTestId("nav-admin-delete");

    fireEvent.click(ingestLink);
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();

    fireEvent.click(deleteLink);
    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();

    fireEvent.click(ingestLink);
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();
  });

  it("keeps the nav rendered while the admin probe is still in flight", () => {
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
    expect(screen.getByTestId("primary-nav")).toHaveAttribute(
      "data-admin-status",
      "loading",
    );
    expect(screen.queryByTestId("nav-admin-ingest")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-delete")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-config")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-chat")).toBeInTheDocument();
  });

  it("shows the Configuration link when /api/admin/status returns 200", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("nav-admin-config")).toBeInTheDocument();
    });
  });

  it("hides the Configuration link when /api/admin/status returns 403", async () => {
    stubFetch({ adminOk: false });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("primary-nav")).toHaveAttribute(
        "data-admin-status",
        "forbidden",
      );
    });
    expect(screen.queryByTestId("nav-admin-config")).not.toBeInTheDocument();
  });

  it("shows the Prompt editor link when /api/admin/status returns 200", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("nav-admin-prompt")).toBeInTheDocument();
    });
  });

  it("hides the Prompt editor link when /api/admin/status returns 403", async () => {
    stubFetch({ adminOk: false });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("primary-nav")).toHaveAttribute(
        "data-admin-status",
        "forbidden",
      );
    });
    expect(screen.queryByTestId("nav-admin-prompt")).not.toBeInTheDocument();
  });

  it("switches to the Configuration view when the Configuration link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const configLink = await screen.findByTestId("nav-admin-config");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    expect(screen.queryByTestId("configuration-page")).not.toBeInTheDocument();

    fireEvent.click(configLink);

    expect(screen.getByTestId("configuration-page")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-admin-config")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId(`nav-${Section.Chat}`)).not.toHaveAttribute(
      "aria-current",
    );
    expect(screen.getByTestId("nav-admin-ingest")).not.toHaveAttribute(
      "aria-current",
    );
    expect(screen.getByTestId("nav-admin-delete")).not.toHaveAttribute(
      "aria-current",
    );
    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
  });

  it("round-trips through all three admin views via the nav links", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const ingestLink = await screen.findByTestId("nav-admin-ingest");
    const deleteLink = screen.getByTestId("nav-admin-delete");
    const configLink = screen.getByTestId("nav-admin-config");

    fireEvent.click(ingestLink);
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("configuration-page")).not.toBeInTheDocument();

    fireEvent.click(deleteLink);
    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("configuration-page")).not.toBeInTheDocument();

    fireEvent.click(configLink);
    expect(screen.getByTestId("configuration-page")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();

    fireEvent.click(ingestLink);
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
    expect(screen.queryByTestId("configuration-page")).not.toBeInTheDocument();
  });

  it("switches to the Prompt editor view when its nav link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const promptLink = await screen.findByTestId("nav-admin-prompt");

    fireEvent.click(promptLink);

    expect(screen.getByTestId("prompt-editor-page")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ingest-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("delete-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("configuration-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-admin-prompt")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("updates the browser URL when an admin nav link is clicked", async () => {
    stubFetch({ adminOk: true });
    render(<App />);
    const ingestLink = await screen.findByTestId("nav-admin-ingest");

    fireEvent.click(ingestLink);

    expect(window.location.pathname).toBe("/admin/ingest");
    expect(screen.getByTestId("ingest-data")).toBeInTheDocument();
  });

  it("deep-links straight to an admin page from its URL", async () => {
    window.history.pushState({}, "", "/admin/delete");
    stubFetch({ adminOk: true });
    render(<App />);

    expect(screen.getByTestId("delete-data")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/admin/delete");
    // Flush the admin probe so the gated nav link settles before teardown.
    await screen.findByTestId("nav-admin-delete");
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

  it("returns to the chat root URL when the Chat nav link is clicked", async () => {
    window.history.pushState({}, "", "/admin/config");
    stubFetch({ adminOk: true });
    render(<App />);
    const chatLink = await screen.findByTestId("nav-chat");

    fireEvent.click(chatLink);

    expect(window.location.pathname).toBe("/");
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });
});
