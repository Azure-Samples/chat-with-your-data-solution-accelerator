/**
 * Frontend identity resolution. `getUserInfo()` reads the signed-in user
 * from the Easy Auth `/.auth/me` endpoint on the SPA's own origin and
 * narrows the principal down to the Entra object-identifier claim, which
 * the backend uses as the per-user partition key. The lookup degrades to
 * `null` whenever no identity provider is configured, the caller is not
 * signed in, or the payload carries no usable object id, so the bootstrap
 * falls back to the default user.
 *
 * The header builder, default-user constant, and resolved-id store live
 * alongside this getter; together they are the single seam every API
 * client spreads to forward `x-ms-client-principal-id`.
 */
import type { AuthMeResponse, UserInfo } from "@/models/auth";

/**
 * Entra object-identifier claim URI. The stable per-user id (the `oid`)
 * the backend partitions chat history on -- preferred over the mutable
 * email / UPN carried in `AuthMeResponse.user_id`.
 */
const OBJECT_ID_CLAIM =
  "http://schemas.microsoft.com/identity/claims/objectidentifier";

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
 * Resolve the signed-in user from Easy Auth `/.auth/me` (the SPA's own
 * origin -- never the backend), narrowing to the object-identifier claim.
 * Returns `null` when `/.auth/me` is unavailable (no identity provider,
 * not signed in), the principal list is empty, or no usable object id is
 * present, so callers fall back to the default user. A failed fetch or
 * malformed payload degrades to `null` rather than throwing -- an absent
 * identity provider is the normal local-dev state, not an error.
 */
export async function getUserInfo(): Promise<UserInfo | null> {
  try {
    const response = await fetch("/.auth/me");
    if (!response.ok) {
      return null;
    }
    const principals = (await response.json()) as AuthMeResponse[];
    const principal = principals[0];
    if (!principal) {
      return null;
    }
    const userId = principal.user_claims.find(
      (claim) => claim.typ === OBJECT_ID_CLAIM,
    )?.val ?? principal.user_id;
    if (!userId) {
      return null;
    }
    return { userId, claims: principal.user_claims };
  } catch {
    return null;
  }
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
 * default. Called once by the auth bootstrap after `/.auth/me` resolves
 * (or settles on the default when no principal is present).
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
