/**
 * Pillar: Stable Core
 * Phase: 1 (Frontend → App Service build-from-source)
 *
 * Runtime backend-URL seam. The deployed SPA is a static bundle served
 * by an App Service; it learns the backend Container App origin at
 * runtime from `GET /config` (served by `frontend_app.py`) instead of
 * baking a backend URL into the bundle at build time. `App.tsx` calls
 * `loadRuntimeConfig()` once at boot; every REST wrapper reads the
 * resolved origin synchronously via `getBackendUrl()`.
 *
 * Fallback order for `getBackendUrl()`:
 *   1. the value fetched from `/config` (once `loadRuntimeConfig`
 *      resolves) -- authoritative in the deployed split-host topology,
 *      where the frontend (App Service) and backend (Container App) are
 *      different origins;
 *   2. the build-time `VITE_BACKEND_URL` (empty when unset), which keeps
 *      local dev against the Vite proxy -- and the existing unit tests --
 *      working unchanged.
 */

const CONFIG_URL = "/config";

interface FrontendConfig {
  backendUrl: string;
}

let cachedBackendUrl: string | null = null;
let inFlight: Promise<void> | null = null;

/**
 * Backend base URL, read synchronously by every REST wrapper. Returns
 * the `/config` value once loaded, else the build-time env fallback.
 */
export function getBackendUrl(): string {
  if (cachedBackendUrl !== null) {
    return cachedBackendUrl;
  }
  return (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";
}

/**
 * Fetch `/config` once and cache `backendUrl`. Idempotent: concurrent
 * and repeat calls share a single in-flight request, and a resolved
 * cache short-circuits without a network round trip. On any failure the
 * cache is left unset so `getBackendUrl()` keeps using the env fallback.
 */
export function loadRuntimeConfig(): Promise<void> {
  if (cachedBackendUrl !== null) {
    return Promise.resolve();
  }
  if (inFlight !== null) {
    return inFlight;
  }
  inFlight = (async () => {
    try {
      const response = await fetch(CONFIG_URL, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const body = (await response.json()) as Partial<FrontendConfig>;
      if (typeof body.backendUrl === "string") {
        cachedBackendUrl = body.backendUrl;
      }
    } catch {
      // Network or parse failure: leave the cache unset so
      // getBackendUrl() falls back to the build-time env value.
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/** Clear cached state. Test-only seam for isolation between cases. */
export function resetRuntimeConfig(): void {
  cachedBackendUrl = null;
  inFlight = null;
}
