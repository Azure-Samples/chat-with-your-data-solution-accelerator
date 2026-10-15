/**
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
  authClientId: string;
  authAuthority: string;
  authApiScope: string;
}

/** Browser-side MSAL (PKCE) parameters resolved from `/config`. */
export interface AuthRuntimeConfig {
  clientId: string;
  authority: string;
  apiScope: string;
}

const EMPTY_AUTH_CONFIG: AuthRuntimeConfig = {
  clientId: "",
  authority: "",
  apiScope: "",
};

let cachedBackendUrl: string | null = null;
let cachedAuthConfig: AuthRuntimeConfig | null = null;
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
 * Browser-side MSAL parameters, read synchronously by the auth
 * bootstrap. Returns the `/config` values once loaded, else an all-empty
 * config so a local dev stack (no identity provider) skips sign-in.
 */
export function getAuthConfig(): AuthRuntimeConfig {
  return cachedAuthConfig ?? EMPTY_AUTH_CONFIG;
}

/**
 * Fetch `/config` once and cache `backendUrl` and the MSAL auth config.
 * Idempotent: concurrent and repeat calls share a single in-flight
 * request, and a resolved cache short-circuits without a network round
 * trip. On any failure the cache is left unset so `getBackendUrl()` keeps
 * using the env fallback and `getAuthConfig()` stays empty.
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
      cachedAuthConfig = {
        clientId: typeof body.authClientId === "string" ? body.authClientId : "",
        authority:
          typeof body.authAuthority === "string" ? body.authAuthority : "",
        apiScope: typeof body.authApiScope === "string" ? body.authApiScope : "",
      };
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
  cachedAuthConfig = null;
  inFlight = null;
}
