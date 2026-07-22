/**
 * Auth state machine for the app shell. Owns the `AuthState`
 * (`userId` / `userInfo` / `phase`) and exposes a single
 * `resolve(userInfo)` action the shell calls once the Easy Auth
 * `/.auth/me` lookup settles. `resolve` keeps the `api/auth.tsx`
 * resolved-id singleton in sync so every API client forwards the right
 * `x-ms-client-principal-id`, and settles the lifecycle phase to
 * `Resolved`:
 *
 *   - a resolved `userInfo` -> forward the real object id;
 *   - no user              -> forward the default user id.
 *
 * The hook holds no effect of its own; the bootstrap effect lives in the
 * shell, which decides what to pass here. Header forwarding flows through
 * the module singleton in `api/auth.tsx`, not React context, so no
 * component below the shell needs to consume this hook.
 */
import { useCallback, useState } from "react";
import { DEFAULT_USER_ID, setUserId } from "@/api/auth";
import { AuthPhase, type AuthState, type UserInfo } from "@/models/auth";

/** Pre-bootstrap state: default user, nothing resolved, still loading. */
const INITIAL_AUTH_STATE: AuthState = {
  userId: DEFAULT_USER_ID,
  userInfo: null,
  phase: AuthPhase.Loading,
};

/** What {@link useAuth} returns: the live state plus its resolve action. */
export interface UseAuthResult {
  auth: AuthState;
  resolve: (userInfo: UserInfo | null) => void;
}

/**
 * Own the app-shell auth state and the single action that settles it. The
 * shell renders the chat experience while `phase` is `Resolved` and a
 * spinner while `Loading`.
 */
export function useAuth(): UseAuthResult {
  const [auth, setAuth] = useState<AuthState>(INITIAL_AUTH_STATE);

  const resolve = useCallback((userInfo: UserInfo | null) => {
    if (userInfo) {
      // A signed-in user resolved: forward their object id everywhere.
      setUserId(userInfo.userId);
      setAuth({
        userId: userInfo.userId,
        userInfo,
        phase: AuthPhase.Resolved,
      });
      return;
    }
    // No signed-in user: fall back to the default user.
    setUserId(null);
    setAuth({
      userId: DEFAULT_USER_ID,
      userInfo: null,
      phase: AuthPhase.Resolved,
    });
  }, []);

  return { auth, resolve };
}
