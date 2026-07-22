/**
 * Auth wire shapes + FE-owned identity state. The browser resolves the
 * signed-in user from the Easy Auth `/.auth/me` endpoint and makes it
 * available app-wide so every API call can forward an
 * `x-ms-client-principal-id` header for per-user partitioning.
 *
 * - `UserClaim` / `AuthMeResponse` mirror the external Easy Auth
 *   `/.auth/me` payload (snake_case, platform-owned -- a boundary wire
 *   shape, not a CWYD-defined contract).
 * - `UserInfo` / `AuthState` are the FE-owned domain shapes held by the
 *   auth store; `phase` is the closed-set resolution lifecycle.
 *
 * The default-user constant and the header / getter helpers live in
 * `api/auth.tsx`, not here -- models declare types only.
 */

/** A single Easy Auth claim from `/.auth/me` (external wire shape). */
export interface UserClaim {
  typ: string;
  val: string;
}

/**
 * One principal entry returned by `/.auth/me`. External Easy Auth wire
 * shape (snake_case, platform-owned); the FE reads `user_claims` to
 * extract the Entra object-identifier claim.
 */
export interface AuthMeResponse {
  user_id: string;
  user_claims: UserClaim[];
  provider_name: string;
}

/** FE-owned resolved identity the app makes available app-wide. */
export interface UserInfo {
  userId: string;
  claims: UserClaim[];
}

/**
 * Closed-set resolution lifecycle for the auth bootstrap. `Loading`
 * while `/.auth/me` is in flight; `Resolved` once a user id is
 * available -- the `/.auth/me` principal when signed in, otherwise the
 * default user.
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
