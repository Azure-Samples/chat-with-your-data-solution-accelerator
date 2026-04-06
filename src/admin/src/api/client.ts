import type { AdminSettings, AppConfig, Document } from "./models";

const API_BASE = "";

async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options?.headers,
        },
    });
    if (!response.ok) {
        const error = await response.text();
        throw new Error(error || `HTTP ${response.status}`);
    }
    return response.json();
}

// FastAPI endpoints (fast ops)
export async function getAdminSettings(): Promise<AdminSettings> {
    return fetchApi("/api/admin/settings");
}

export async function getDocuments(): Promise<{ documents: Document[] }> {
    return fetchApi("/api/admin/documents");
}

export async function deleteDocuments(ids: string[]): Promise<void> {
    await fetchApi("/api/admin/documents", {
        method: "DELETE",
        body: JSON.stringify({ ids }),
    });
}

export async function getConfig(): Promise<AppConfig> {
    return fetchApi("/api/admin/config");
}

export async function updateConfig(config: AppConfig): Promise<void> {
    await fetchApi("/api/admin/config", {
        method: "PUT",
        body: JSON.stringify(config),
    });
}

export async function getUploadSas(): Promise<{ sas_url: string }> {
    return fetchApi("/api/admin/upload-sas", { method: "POST" });
}

// Azure Functions direct calls (long-running ops)
export async function callAddUrlEmbeddings(
    functionUrl: string,
    functionKey: string,
    url: string
): Promise<Response> {
    return fetch(`${functionUrl}/api/AddURLEmbeddings?code=${functionKey}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    });
}

export async function callBatchStart(
    functionUrl: string,
    functionKey: string
): Promise<Response> {
    return fetch(`${functionUrl}/api/BatchStartProcessing?code=${functionKey}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ process_all: true }),
    });
}
