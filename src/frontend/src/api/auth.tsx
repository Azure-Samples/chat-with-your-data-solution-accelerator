/**
 * Frontend identity resolution. `getUserInfo()` drives the browser-side
 * MSAL (PKCE) flow via the `api/msal` seam to resolve the signed-in user
 * and a backend-audience access token. The object id becomes the per-user
 * partition key and the access token the bearer every API client forwards.
 * The lookup degrades to `null` whenever no identity provider is
 * configured (local dev) or the browser is mid-redirect, so the bootstrap
 * falls back to the default user.
 *
 * The header builder, default-user constant, and resolved-id store live
 * alongside this getter; together they are the single seam every API
 * client spreads to forward `x-ms-client-principal-id` + `Authorization`.
 */
import { getMsalApp, resolveAuthWith } from "@/api/msal";
import { getAuthConfig } from "@/api/runtimeConfig";
import type { UserInfo } from "@/models/auth";

/**
 * Identity header every API client forwards for per-user partitioning.
 * A browser-set value is forgeable and is **not** a trust boundary -- the
 * backend validates only that it is a GUID and otherwise treats it as the
 * shared default partition. Real authentication, when enabled, is enforced
 * at the ingress/proxy (Easy Auth injecting/overwriting this header), never
 * in backend application code.
 */
const PRINCIPAL_ID_HEADER = "x-ms-client-principal-id";

/**
 * The all-zeros id forwarded when no signed-in user has been resolved.
 * The backend treats it as a single shared partition for local /
 * unauthenticated use.
 */
export const DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000";

/**
 * The resolved per-user id, set once the bootstrap resolves the signed-in
 * user (or the default). `null` until {@link setUserId} runs, so
 * {@link getUserId} falls back to {@link DEFAULT_USER_ID} during the
 * initial load.
 */
let currentUserId: string | null = null;

/**
 * Resolve the signed-in user through the browser-side MSAL flow, reading
 * the client id / authority / backend scope from the runtime config.
 * Returns `null` when no identity provider is configured (`getMsalApp`
 * yields no app) or the browser is navigating through a login / token
 * redirect (`resolveAuthWith` yields no result yet), so callers fall back
 * to the default user. `loadRuntimeConfig()` must have resolved before
 * this runs so the auth config is populated.
 */
export async function getUserInfo(): Promise<UserInfo | null> {
  const authConfig = getAuthConfig();
  const app = await getMsalApp(authConfig);
  if (!app) {
    return null;
  }
  // Forward the ID token (audience = client id), so OIDC scopes suffice;
  // a configured apiScope is honoured when present for forward-compat.
  const scopes = authConfig.apiScope
    ? [authConfig.apiScope]
    : ["openid", "profile"];
  const resolved = await resolveAuthWith(app, scopes);
  if (!resolved) {
    return null;
  }
  return {
    userId: resolved.userId,
    claims: resolved.claims,
    accessToken: resolved.accessToken,
  };
}

/**
 * The id forwarded on every API request: the resolved signed-in user when
 * available, else {@link DEFAULT_USER_ID}. A module-level singleton so the
 * header builder stays synchronous and dependency-free at each call site.
 */
export function getUserId(): string {
  return currentUserId ?? DEFAULT_USER_ID;
}

/**
 * Record the resolved per-user id so subsequent {@link userIdHeaders}
 * calls forward it; passing `null` clears the override back to the
 * default. Called once by the auth bootstrap after the MSAL flow
 * resolves (or settles on the default when no user is present).
 */
export function setUserId(userId: string | null): void {
  currentUserId = userId;
}

/**
 * Build the per-user identity header every API client spreads onto its
 * request: `{ "x-ms-client-principal-id": <resolved id> }`. The single
 * source of the forwarded principal id -- clients never assemble it inline.
 */
export function userIdHeaders(): Record<string, string> {
  return { [PRINCIPAL_ID_HEADER]: getUserId() };
}

/**
 * The backend-audience bearer token (the MSAL id token) resolved by the
 * auth bootstrap, or `null` when none was issued (local dev, or no
 * identity provider is configured). A module-level singleton so
 * {@link authHeaders} stays synchronous and dependency-free at each call
 * site -- set once by the auth bootstrap, exactly like {@link setUserId}.
 */
let currentAccessToken: string | null = null;

/**
 * Record the backend bearer token so subsequent {@link authHeaders} calls
 * forward it; `null` clears it. Called by the auth bootstrap after the
 * MSAL flow resolves (alongside {@link setUserId}).
 */
export function setAccessToken(token: string | null): void {
  currentAccessToken = token;
}

/** The resolved backend bearer token, or `null` when none is available. */
export function getAccessToken(): string | null {
  return currentAccessToken;
}

/**
 * Build the `Authorization: Bearer <token>` header every backend API
 * client spreads onto its request. Returns an empty object when no token
 * has been resolved, so local dev (no identity provider) and the existing
 * unit tests keep working unchanged -- the header is simply absent and the
 * backend's `AZURE_REQUIRE_ADMIN_AUTH` gate stays disabled on loopback.
 * This is the real trust credential; `userIdHeaders()` is only a
 * partition hint. The single source of the forwarded bearer token --
 * clients never assemble it inline.
 */
export function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
