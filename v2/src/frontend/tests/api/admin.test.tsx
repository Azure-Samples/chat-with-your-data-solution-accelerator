/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Vitest suite for the `getAdminStatus()` REST client. Mocks global
 * `fetch` with a JSON body so the unit test runs offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getAdminStatus } from "../../src/api/admin";
import type { AdminStatus } from "../../src/models/admin";

function jsonResponse(body: unknown, { status = 200 }: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const STATUS_FIXTURE: AdminStatus = {
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
  cors_origins: ["http://localhost:5273"],
  version: "2.0.0",
};

describe("getAdminStatus", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("GETs /api/admin/status with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_FIXTURE));

    await getAdminStatus();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/status");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_FIXTURE));

    const result = await getAdminStatus();

    expect(result).toEqual(STATUS_FIXTURE);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(getAdminStatus()).rejects.toThrow(/status 401/);
  });

  it("throws on 403 (authenticated but not in admin role)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Caller is not in the 'admin' role." },
        { status: 403 },
      ),
    );

    await expect(getAdminStatus()).rejects.toThrow(/status 403/);
  });

  it("throws on 503 (backend not ready)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Backend not ready." }, { status: 503 }),
    );

    await expect(getAdminStatus()).rejects.toThrow(/status 503/);
  });
});
