/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Vitest suite for the admin REST client. Mocks global `fetch` with
 * JSON bodies so unit tests run offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addDocumentUrl,
  deleteDocument,
  getAdminConfig,
  getAdminStatus,
  listDocuments,
  patchAdminConfig,
  reprocessAll,
  uploadDocument,
} from "@/api/admin";
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

const INGEST_URL_FIXTURE: IngestUrlResponse = {
  ingestion_job_id: "11111111-1111-1111-1111-111111111111",
  url: "https://docs.example.com/article",
  document_count: 7,
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
};

const RUNTIME_CONFIG_FIXTURE: RuntimeConfig = {
  orchestrator_name: "agent_framework",
  openai_temperature: 0.7,
  openai_max_tokens: null,
  search_use_semantic_search: null,
  search_top_k: null,
  log_level: null,
  content_safety_enabled: null,
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

  it("GETs /api/admin/config with a JSON Accept header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(ADMIN_CONFIG_FIXTURE));

    await getAdminConfig();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/config");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Accept).toBe(
      "application/json",
    );
  });

  it("returns the typed seven-field payload on 200", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(ADMIN_CONFIG_FIXTURE));

    const result = await getAdminConfig();

    expect(result).toEqual(ADMIN_CONFIG_FIXTURE);
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
