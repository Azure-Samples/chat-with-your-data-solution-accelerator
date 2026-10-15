/**
 * Resolve the "Open document" deep-link target for a citation.
 *
 * v2 ingestion records a document's blob name in `Citation.title` and
 * leaves `Citation.url` empty for files uploaded to blob storage; for
 * documents added from an external address the URL is carried in
 * `title` instead. This helper maps either shape onto a single link:
 *
 * - blob storage URL in `url` -> rewrite to the backend file route so
 *   the browser fetches it through `/api/files/<name>` (the raw blob
 *   URL would need a SAS token the browser does not hold);
 * - any other http(s) `url` -> use it verbatim (bring-your-own-data);
 * - empty `url`, http(s) `title` -> external document, use `title`;
 * - empty `url`, plain `title` -> blob document, build the backend
 *   file route from the blob name in `title`;
 * - nothing usable -> `null` (caller omits the link).
 *
 * The backend file route is absolute (prefixed with the runtime
 * `getBackendUrl()` origin from `/config`, not the build-time
 * `VITE_BACKEND_URL`) because the link is a top-level navigation: in the
 * deployed split-host topology the frontend and backend are separate
 * origins, and a relative `/api/files/...` would resolve against the
 * static frontend host (which serves the SPA, not the file).
 */
import type { Citation } from "@/models/chat";
import { getBackendUrl } from "@/api/runtimeConfig";

const BLOB_HOST_FRAGMENT = ".blob.core.windows.net";

/**
 * Classified "Open document" target for a citation. An `external`
 * document is a plain http(s) URL the browser opens directly; a `file`
 * document is a blob stored behind the backend Easy Auth gate, reachable
 * only by the authenticated `/api/files/<name>` fetch (a bearer-less
 * top-level navigation is rejected with 401).
 */
export type CitationDocument =
  | { kind: "external"; url: string }
  | { kind: "file"; filename: string };

function isHttpUrl(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

function isAzureBlobHost(rawUrl: string): boolean {
  try {
    const host = new URL(rawUrl).hostname.toLowerCase();
    return host === "blob.core.windows.net" || host.endsWith(BLOB_HOST_FRAGMENT);
  } catch {
    return false;
  }
}

function filesHref(filename: string): string {
  return `${getBackendUrl()}/api/files/${encodeURIComponent(filename)}`;
}

function lastPathSegment(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    const segments = parsed.pathname
      .split("/")
      .filter((segment) => segment.length > 0);
    return decodeURIComponent(segments.at(-1) ?? "");
  } catch {
    return "";
  }
}

/**
 * Classify a citation's document target as an external URL (open
 * directly) or a backend-gated file (fetch with the bearer). Returns
 * `null` when neither `url` nor `title` yields a usable target.
 */
export function resolveCitationDocument(citation: Citation): CitationDocument | null {
  const url = citation.url;
  if (isHttpUrl(url)) {
    if (isAzureBlobHost(url)) {
      const filename = lastPathSegment(url);
      return filename.length > 0 ? { kind: "file", filename } : null;
    }
    return { kind: "external", url };
  }
  const title = citation.title;
  if (isHttpUrl(title)) {
    return { kind: "external", url: title };
  }
  if (title.length > 0) {
    return { kind: "file", filename: title };
  }
  return null;
}

export function deriveDocumentHref(citation: Citation): string | null {
  const doc = resolveCitationDocument(citation);
  if (doc === null) {
    return null;
  }
  return doc.kind === "external" ? doc.url : filesHref(doc.filename);
}
