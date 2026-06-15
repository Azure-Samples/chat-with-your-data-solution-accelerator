/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
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
 * The backend file route is absolute (prefixed with `VITE_BACKEND_URL`)
 * because the link is a top-level navigation: in the deployed topology
 * the frontend and backend are separate origins, and a relative
 * `/api/files/...` would resolve against the static frontend host.
 */
import type { Citation } from "@/models/chat";

const BLOB_HOST_FRAGMENT = ".blob.core.windows.net";

function backendUrl(): string {
  return (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";
}

function isHttpUrl(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

function filesHref(filename: string): string {
  return `${backendUrl()}/api/files/${encodeURIComponent(filename)}`;
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

export function deriveDocumentHref(citation: Citation): string | null {
  const url = citation.url;
  if (isHttpUrl(url)) {
    if (url.includes(BLOB_HOST_FRAGMENT)) {
      const filename = lastPathSegment(url);
      return filename.length > 0 ? filesHref(filename) : null;
    }
    return url;
  }
  const title = citation.title;
  if (isHttpUrl(title)) {
    return title;
  }
  if (title.length > 0) {
    return filesHref(title);
  }
  return null;
}
