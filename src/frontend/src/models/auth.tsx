/**
 * Auth wire shapes + FE-owned identity state. The browser resolves the
 * signed-in user through the MSAL (PKCE) flow and makes it available
 * app-wide so every API call can forward an `x-ms-client-principal-id`
 * header for per-user partitioning plus the backend bearer token.
 *
 * - `UserClaim` mirrors a single MSAL id-token claim (`typ` / `val`).
 * - `UserInfo` / `AuthState` are the FE-owned domain shapes held by the
 *   auth store; `phase` is the closed-set resolution lifecycle.
 *
 * The default-user constant and the header / getter helpers live in
 * `api/auth.tsx`, not here -- models declare types only.
 */

/** A single identity claim resolved from the MSAL id token. */
export interface UserClaim {
  typ: string;
  val: string;
}

/** FE-owned resolved identity the app makes available app-wide. */
export interface UserInfo {
  userId: string;
  claims: UserClaim[];
  /**
   * Backend-audience bearer token (the MSAL id token), or `null` when
   * none was issued (local dev / provider not configured). Spread onto
   * backend requests via `authHeaders()`.
   */
  accessToken?: string | null;
}

/**
 * Closed-set resolution lifecycle for the auth bootstrap. `Loading`
 * while the MSAL identity lookup is in flight; `Resolved` once a user id
 * is available -- the signed-in user when present, otherwise the default
 * user.
 */
export const AuthPhase = {
  Loading: "loading",
  Resolved: "resolved",
} as const;
export type AuthPhase = (typeof AuthPhase)[keyof typeof AuthPhase];

/** FE-owned auth state held by the auth store (see `api/auth.tsx`). */
export interface AuthState {
  userId: string;
  userInfo: UserInfo | null;
  phase: AuthPhase;
}
