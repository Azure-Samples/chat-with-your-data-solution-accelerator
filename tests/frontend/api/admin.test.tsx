/**
 * Vitest suite for the admin REST client. Mocks global `fetch` with
 * JSON bodies so unit tests run offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addDocumentUrl,
  deleteDocument,
  getAdminConfig,
  getAdminStatus,
  getAssistantTypePresets,
  listDocuments,
  patchAdminConfig,
  reprocessAll,
  resetAdminConfig,
  uploadDocument,
} from "@/api/admin";
import { DEFAULT_USER_ID, setUserId } from "@/api/auth";
import { loadRuntimeConfig, resetRuntimeConfig } from "@/api/runtimeConfig";
import type {
  AdminConfig,
  AdminStatus,
  DeleteDocumentResponse,
  IngestUrlResponse,
  ListDocumentsResponse,
  ReprocessResponse,
  RuntimeConfig,
  UploadResponse,
} from "@/models/admin";

// loadRuntimeConfig is mocked to a no-op for every test in this file so that
// apiUrl() does not consume a test's fetch mock with a /config preflight.
// The "admin backendUrl runtime /config seam" describe block temporarily
// restores the real implementation to validate the runtime-URL seam.
vi.mock("@/api/runtimeConfig", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/api/runtimeConfig")>();
  return {
    ...mod,
    loadRuntimeConfig: vi.fn().mockResolvedValue(undefined),
  };
});

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
  search_enabled: true,
  app_insights_enabled: false,
  cors_origins: ["http://localhost:5273"],
  version: "2.0.0",
};

const INGEST_URL_FIXTURE: IngestUrlResponse = {
  url: "https://docs.example.com/article",
  filename: "docs.example.com_article.txt",
  blob_path: "documents/docs.example.com_article.txt",
  ingestion_job_id: "11111111-1111-1111-1111-111111111111",
  queued: true,
};

const UPLOAD_FIXTURE: UploadResponse = {
  filename: "test.pdf",
  blob_path: "documents/test.pdf",
  ingestion_job_id: "22222222-2222-2222-2222-222222222222",
  queued: true,
};

const REPROCESS_FIXTURE: ReprocessResponse = {
  ingestion_job_id: "33333333-3333-3333-3333-333333333333",
  enqueued_count: 42,
};

const LIST_DOCUMENTS_FIXTURE: ListDocumentsResponse = {
  documents: [
    { source: "alpha.pdf", chunk_count: 3, last_modified: null },
    { source: "beta.pdf", chunk_count: 7, last_modified: null },
  ],
  total: 2,
};

const DELETE_DOCUMENT_FIXTURE: DeleteDocumentResponse = {
  deleted: 5,
};

const ADMIN_CONFIG_FIXTURE: AdminConfig = {
  orchestrator_name: "langgraph",
  openai_temperature: 0.0,
  openai_max_tokens: 4096,
  search_use_semantic_search: true,
  search_top_k: 5,
  log_level: "INFO",
  content_safety_enabled: false,
  cwyd_agent_instructions: "You are the Chat With Your Data assistant.",
  ai_assistant_type: "default",
  post_answering_prompt: "",
  post_answering_enabled: false,
  post_answering_filter_message: "",
};

const RUNTIME_CONFIG_FIXTURE: RuntimeConfig = {
  orchestrator_name: "agent_framework",
  openai_temperature: 0.7,
  openai_max_tokens: null,
  search_use_semantic_search: null,
  search_top_k: null,
  log_level: null,
  content_safety_enabled: null,
  cwyd_agent_instructions: null,
  ai_assistant_type: null,
  post_answering_prompt: null,
  post_answering_enabled: null,
  post_answering_filter_message: null,
  updated_at: "2026-06-03T11:00:00Z",
  updated_by: "admin-user-id",
};

// The effective endpoint envelopes the override-resolved config. Here the
// operator has pinned the orchestrator to agent_framework, so `values`
// carries that instead of the langgraph env default: save
// agent_framework -> reload must keep agent_framework.
const EFFECTIVE_CONFIG_FIXTURE = {
  values: { ...ADMIN_CONFIG_FIXTURE, orchestrator_name: "agent_framework" },
  sources: {
    orchestrator_name: "override",
    openai_temperature: "env",
    openai_max_tokens: "env",
    search_use_semantic_search: "env",
    search_top_k: "env",
    log_level: "env",
    content_safety_enabled: "env",
    cwyd_agent_instructions: "env",
    ai_assistant_type: "env",
    post_answering_prompt: "env",
    post_answering_enabled: "env",
    post_answering_filter_message: "env",
  },
  assistant_type_presets: {
    default: "You are the Chat With Your Data assistant.",
    "contract assistant": "You are an AI Contract Assistant.",
    "employee assistant": "You are an AI HR Assistant.",
  },
  updated_at: "2026-06-03T11:00:00Z",
  updated_by: "admin-user-id",
};

describe("getAdminStatus", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
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

  it("prepends VITE_BACKEND_URL to the status route when set", async () => {
    // The deployed topology splits the frontend (App Service) and backend
    // (Container App) across origins. A relative `/api/admin/status` would
    // hit the SPA catch-all and return index.html (200 HTML), so the admin
    // probe must target the backend origin to receive JSON and reveal the
    // Admin button.
    vi.stubEnv("VITE_BACKEND_URL", "https://backend.example.com");
    fetchMock.mockResolvedValueOnce(jsonResponse(STATUS_FIXTURE));

    await getAdminStatus();

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://backend.example.com/api/admin/status");
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

describe("addDocumentUrl", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs /api/admin/documents/url with a JSON body carrying the URL", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(INGEST_URL_FIXTURE));

    await addDocumentUrl("https://docs.example.com/article");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents/url");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      url: "https://docs.example.com/article",
    });
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(INGEST_URL_FIXTURE));

    const result = await addDocumentUrl("https://docs.example.com/article");

    expect(result).toEqual(INGEST_URL_FIXTURE);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(
      addDocumentUrl("https://docs.example.com/article"),
    ).rejects.toThrow(/status 401/);
  });

  it("throws on 422 (invalid URL shape)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Invalid URL." }, { status: 422 }),
    );

    await expect(addDocumentUrl("not a url")).rejects.toThrow(/status 422/);
  });

  it("throws on 503 (storage or search not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Document storage is not configured." },
        { status: 503 },
      ),
    );

    await expect(
      addDocumentUrl("https://docs.example.com/article"),
    ).rejects.toThrow(/status 503/);
  });
});

describe("uploadDocument", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function makeFile(name = "test.pdf", contents = "hello pdf"): File {
    return new File([contents], name, { type: "application/pdf" });
  }

  it("POSTs /api/admin/documents with a multipart body carrying the file part", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(UPLOAD_FIXTURE));
    const file = makeFile();

    await uploadDocument(file);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
    expect(init.body).toBeInstanceOf(FormData);
    const formPart = (init.body as FormData).get("file");
    expect(formPart).toBeInstanceOf(File);
    expect((formPart as File).name).toBe("test.pdf");
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(UPLOAD_FIXTURE));

    const result = await uploadDocument(makeFile());

    expect(result).toEqual(UPLOAD_FIXTURE);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(uploadDocument(makeFile())).rejects.toThrow(/status 401/);
  });

  it("throws on 413 (oversize)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: { msg: "Uploaded file exceeds the maximum allowed size." } },
        { status: 413 },
      ),
    );

    await expect(uploadDocument(makeFile())).rejects.toThrow(/status 413/);
  });

  it("throws on 415 (unsupported extension)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: { msg: "Unsupported file extension.", extension: "exe" } },
        { status: 415 },
      ),
    );

    await expect(uploadDocument(makeFile("malware.exe"))).rejects.toThrow(
      /status 415/,
    );
  });

  it("throws on 503 (storage not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Document storage is not configured." },
        { status: 503 },
      ),
    );

    await expect(uploadDocument(makeFile())).rejects.toThrow(/status 503/);
  });
});

describe("reprocessAll", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs /api/admin/documents/reprocess with no body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(REPROCESS_FIXTURE));

    await reprocessAll();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents/reprocess");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
    expect(init.body).toBeUndefined();
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(REPROCESS_FIXTURE));

    const result = await reprocessAll();

    expect(result).toEqual(REPROCESS_FIXTURE);
  });

  it("returns null ingestion_job_id when the container was empty", async () => {
    const emptyFixture: ReprocessResponse = {
      ingestion_job_id: null,
      enqueued_count: 0,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyFixture));

    const result = await reprocessAll();

    expect(result.ingestion_job_id).toBeNull();
    expect(result.enqueued_count).toBe(0);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(reprocessAll()).rejects.toThrow(/status 401/);
  });

  it("throws on 503 (storage or queue not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Document storage is not configured." },
        { status: 503 },
      ),
    );

    await expect(reprocessAll()).rejects.toThrow(/status 503/);
  });
});

describe("listDocuments", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("GETs /api/admin/documents with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(LIST_DOCUMENTS_FIXTURE));

    await listDocuments();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(LIST_DOCUMENTS_FIXTURE));

    const result = await listDocuments();

    expect(result).toEqual(LIST_DOCUMENTS_FIXTURE);
  });

  it("returns an empty list on 200 with no sources", async () => {
    const empty: ListDocumentsResponse = { documents: [], total: 0 };
    fetchMock.mockResolvedValueOnce(jsonResponse(empty));

    const result = await listDocuments();

    expect(result).toEqual(empty);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(listDocuments()).rejects.toThrow(/status 401/);
  });

  it("throws on 503 (search not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Search backend is not configured for this deployment." },
        { status: 503 },
      ),
    );

    await expect(listDocuments()).rejects.toThrow(/status 503/);
  });
});

describe("deleteDocument", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("DELETEs /api/admin/documents/{source} with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(DELETE_DOCUMENT_FIXTURE));

    await deleteDocument("report.pdf");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents/report.pdf");
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("URL-encodes special characters in the source segment", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(DELETE_DOCUMENT_FIXTURE));

    await deleteDocument("annual report 2024.pdf");

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/documents/annual%20report%202024.pdf");
  });

  it("returns the typed payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(DELETE_DOCUMENT_FIXTURE));

    const result = await deleteDocument("report.pdf");

    expect(result).toEqual(DELETE_DOCUMENT_FIXTURE);
  });

  it("throws on 404 (no chunks matched the source)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "No indexed chunks found for source 'missing.pdf'." },
        { status: 404 },
      ),
    );

    await expect(deleteDocument("missing.pdf")).rejects.toThrow(/status 404/);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(deleteDocument("report.pdf")).rejects.toThrow(/status 401/);
  });

  it("throws on 503 (search not configured)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Search backend is not configured for this deployment." },
        { status: 503 },
      ),
    );

    await expect(deleteDocument("report.pdf")).rejects.toThrow(/status 503/);
  });
});

describe("getAdminConfig", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("GETs /api/admin/config/effective with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(EFFECTIVE_CONFIG_FIXTURE));

    await getAdminConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/config/effective");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("returns the override-resolved values unwrapped from the effective envelope", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(EFFECTIVE_CONFIG_FIXTURE));

    const result = await getAdminConfig();

    // The persisted override wins: agent_framework, not the langgraph default.
    expect(result).toEqual(EFFECTIVE_CONFIG_FIXTURE.values);
    expect(result.orchestrator_name).toBe("agent_framework");
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(getAdminConfig()).rejects.toThrow(/status 401/);
  });

  it("throws on 403 (authenticated but not in admin role)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Caller is not in the 'admin' role." },
        { status: 403 },
      ),
    );

    await expect(getAdminConfig()).rejects.toThrow(/status 403/);
  });

  it("throws on 503 (backend not ready)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Backend not ready." }, { status: 503 }),
    );

    await expect(getAdminConfig()).rejects.toThrow(/status 503/);
  });
});

describe("getAssistantTypePresets", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("GETs /api/admin/config/effective with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(EFFECTIVE_CONFIG_FIXTURE));

    await getAssistantTypePresets();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/config/effective");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("returns the assistant_type_presets map unwrapped from the envelope", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(EFFECTIVE_CONFIG_FIXTURE));

    const result = await getAssistantTypePresets();

    expect(result).toEqual(EFFECTIVE_CONFIG_FIXTURE.assistant_type_presets);
    expect(result["contract assistant"]).toBe(
      "You are an AI Contract Assistant.",
    );
  });

  it("throws on 403 (authenticated but not in admin role)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Caller is not in the 'admin' role." },
        { status: 403 },
      ),
    );

    await expect(getAssistantTypePresets()).rejects.toThrow(/status 403/);
  });
});

describe("patchAdminConfig", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("PATCHes /api/admin/config with JSON content and Accept headers", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await patchAdminConfig({ openai_temperature: 0.7 });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/config");
    expect(init.method).toBe("PATCH");
    const headers = init.headers as Record<string, string>;
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("serializes explicit-set values verbatim", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await patchAdminConfig({
      orchestrator_name: "agent_framework",
      openai_temperature: 0.7,
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      orchestrator_name: "agent_framework",
      openai_temperature: 0.7,
    });
  });

  it("preserves explicit null values (RFC 7396 'clear override')", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await patchAdminConfig({
      openai_temperature: null,
      content_safety_enabled: null,
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // JSON.stringify preserves explicit null but drops undefined,
    // so the wire shape must carry null for fields the operator is
    // asking the server to revert to env-default.
    expect(JSON.parse(init.body as string)).toEqual({
      openai_temperature: null,
      content_safety_enabled: null,
    });
  });

  it("sends an empty body for an empty patch (touch-only PATCH)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await patchAdminConfig({});

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({});
  });

  it("returns the typed RuntimeConfig payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    const result = await patchAdminConfig({ openai_temperature: 0.7 });

    expect(result).toEqual(RUNTIME_CONFIG_FIXTURE);
  });

  it("throws on 422 (unknown field or wrong type)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: { msg: "Unknown field(s) in PATCH body" } },
        { status: 422 },
      ),
    );

    await expect(
      patchAdminConfig({ openai_temperature: 0.7 }),
    ).rejects.toThrow(/status 422/);
  });

  it("throws on 401 (missing or malformed Easy Auth)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not authenticated." }, { status: 401 }),
    );

    await expect(
      patchAdminConfig({ openai_temperature: 0.7 }),
    ).rejects.toThrow(/status 401/);
  });

  it("throws on 403 (authenticated but not in admin role)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Caller is not in the 'admin' role." },
        { status: 403 },
      ),
    );

    await expect(
      patchAdminConfig({ openai_temperature: 0.7 }),
    ).rejects.toThrow(/status 403/);
  });
});

describe("resetAdminConfig", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("PATCHes /api/admin/config (delegates to patchAdminConfig)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await resetAdminConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/config");
    expect(init.method).toBe("PATCH");
    const headers = init.headers as Record<string, string>;
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("clears every writable override field with an explicit null", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    await resetAdminConfig();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // Every writable field must ride the wire as an explicit null so the
    // backend clears the override (RFC 7396) and the field reverts to its
    // env / built-in default. The full-object match doubles as a lockstep
    // guard: a new writable field added without a null entry fails here.
    expect(JSON.parse(init.body as string)).toEqual({
      orchestrator_name: null,
      openai_temperature: null,
      openai_max_tokens: null,
      search_use_semantic_search: null,
      search_top_k: null,
      log_level: null,
      content_safety_enabled: null,
      cwyd_agent_instructions: null,
      ai_assistant_type: null,
      post_answering_prompt: null,
      post_answering_enabled: null,
      post_answering_filter_message: null,
    });
  });

  it("returns the typed RuntimeConfig payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(RUNTIME_CONFIG_FIXTURE));

    const result = await resetAdminConfig();

    expect(result).toEqual(RUNTIME_CONFIG_FIXTURE);
  });

  it("throws AdminApiError on 403 (not in admin role)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Caller is not in the 'admin' role." },
        { status: 403 },
      ),
    );

    await expect(resetAdminConfig()).rejects.toThrow(/status 403/);
  });
});

describe("principal id header forwarding", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    // Admin calls forward the shared auth singleton; reset it.
    setUserId(null);
  });

  const RESOLVED_ID = "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab";

  const calls: {
    name: string;
    fixture: unknown;
    invoke: () => Promise<unknown>;
  }[] = [
    { name: "getAdminStatus", fixture: STATUS_FIXTURE, invoke: getAdminStatus },
    {
      name: "addDocumentUrl",
      fixture: INGEST_URL_FIXTURE,
      invoke: () => addDocumentUrl("https://docs.example.com/article"),
    },
    {
      name: "uploadDocument",
      fixture: UPLOAD_FIXTURE,
      invoke: () =>
        uploadDocument(
          new File(["pdf"], "test.pdf", { type: "application/pdf" }),
        ),
    },
    { name: "reprocessAll", fixture: REPROCESS_FIXTURE, invoke: reprocessAll },
    { name: "listDocuments", fixture: LIST_DOCUMENTS_FIXTURE, invoke: listDocuments },
    {
      name: "deleteDocument",
      fixture: DELETE_DOCUMENT_FIXTURE,
      invoke: () => deleteDocument("report.pdf"),
    },
    {
      name: "getAdminConfig",
      fixture: EFFECTIVE_CONFIG_FIXTURE,
      invoke: getAdminConfig,
    },
    {
      name: "getAssistantTypePresets",
      fixture: EFFECTIVE_CONFIG_FIXTURE,
      invoke: getAssistantTypePresets,
    },
    {
      name: "patchAdminConfig",
      fixture: RUNTIME_CONFIG_FIXTURE,
      invoke: () => patchAdminConfig({ orchestrator_name: "langgraph" }),
    },
    {
      name: "resetAdminConfig",
      fixture: RUNTIME_CONFIG_FIXTURE,
      invoke: resetAdminConfig,
    },
  ];

  it.each(calls)(
    "$name forwards the default principal id header when no user is resolved",
    async ({ fixture, invoke }) => {
      fetchMock.mockResolvedValueOnce(jsonResponse(fixture));
      await invoke();
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["x-ms-client-principal-id"]).toBe(DEFAULT_USER_ID);
    },
  );

  it.each(calls)(
    "$name forwards the resolved principal id header once a user is set",
    async ({ fixture, invoke }) => {
      setUserId(RESOLVED_ID);
      fetchMock.mockResolvedValueOnce(jsonResponse(fixture));
      await invoke();
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["x-ms-client-principal-id"]).toBe(RESOLVED_ID);
    },
  );
});

describe("admin backendUrl runtime /config seam", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    // Restore the real loadRuntimeConfig so these tests can validate
    // that apiUrl() uses the URL fetched from /config.
    const realMod = await vi.importActual<typeof import("@/api/runtimeConfig")>("@/api/runtimeConfig");
    vi.mocked(loadRuntimeConfig).mockImplementation(realMod.loadRuntimeConfig);
    resetRuntimeConfig();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.mocked(loadRuntimeConfig).mockResolvedValue(undefined);
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    resetRuntimeConfig();
  });

  it("prefers the runtime /config backendUrl over the env fallback", async () => {
    // The runtime origin from /config must win over the build-time
    // VITE_BACKEND_URL so the deployed split-host SPA crosses to the
    // backend Container App resolved at boot, not a baked-in guess.
    vi.stubEnv("VITE_BACKEND_URL", "https://build-time.example.com");
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/config") {
        return jsonResponse({ backendUrl: "https://runtime.example.com" });
      }
      return jsonResponse(STATUS_FIXTURE);
    });

    await loadRuntimeConfig();
    await getAdminStatus();

    const statusCall = fetchMock.mock.calls.find(
      ([callUrl]) => callUrl === "https://runtime.example.com/api/admin/status",
    );
    expect(statusCall).toBeDefined();
  });
});
