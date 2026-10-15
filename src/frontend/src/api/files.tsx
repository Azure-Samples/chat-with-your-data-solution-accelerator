/**
 * REST client for the document-file surface. `/api/files/<name>` sits
 * behind the backend Easy Auth gate, so a plain top-level navigation
 * (an `<a href>` straight to the backend origin) is rejected with 401 --
 * the browser never attaches the MSAL bearer to a navigation. This
 * client fetches the blob with the forwarded bearer + principal id like
 * every other backend call, then hands back an object URL the UI can
 * open in a new tab for inline viewing.
 */
import { authHeaders, userIdHeaders } from "@/api/auth";
import { getBackendUrl, loadRuntimeConfig } from "@/api/runtimeConfig";

const FILES_URL = "/api/files";

/** Join the backend base (trailing slash trimmed) with an API path.
 * Awaits `loadRuntimeConfig()` so the URL resolves against the real
 * backend origin, never the SPA catch-all. */
async function apiUrl(path: string): Promise<string> {
  await loadRuntimeConfig();
  return `${getBackendUrl().replace(/\/$/, "")}${path}`;
}

/**
 * Fetch a stored document blob by filename through the authenticated
 * backend route and return an object URL for it. Throws on a non-2xx
 * response. The caller owns the returned URL and should revoke it with
 * `URL.revokeObjectURL` once the consumer no longer needs it.
 */
export async function fetchDocumentObjectUrl(filename: string): Promise<string> {
  const url = await apiUrl(`${FILES_URL}/${encodeURIComponent(filename)}`);
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "*/*", ...userIdHeaders(), ...authHeaders() },
  });
  if (!response.ok) {
    throw new Error(
      `fetchDocumentObjectUrl: request failed with status ${response.status}`,
    );
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
