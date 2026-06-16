/**
 * Pillar: Stable Core
 * Phase: 5 (frontend — user identity)
 *
 * Auth state machine for the app shell. Owns the `AuthState`
 * (`userId` / `userInfo` / `authEnforced` / `phase`) and exposes a single
 * `resolve(authEnforced, userInfo)` action the shell calls once after the
 * health probe and `/.auth/me` lookup settle. `resolve` keeps the
 * `api/auth.tsx` resolved-id singleton in sync so every API client
 * forwards the right `x-ms-client-principal-id`, and transitions the
 * lifecycle phase:
 *
 *   - a resolved `userInfo`        -> `Resolved` (forward the real id);
 *   - no user but auth not enforced -> `Resolved` (forward the default);
 *   - no user but auth enforced     -> `Blocked` (shell shows the error
 *     screen and makes no API calls).
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
  authEnforced: false,
  phase: AuthPhase.Loading,
};

/** What {@link useAuth} returns: the live state plus its resolve action. */
export interface UseAuthResult {
  auth: AuthState;
  resolve: (authEnforced: boolean, userInfo: UserInfo | null) => void;
}

/**
 * Own the app-shell auth state and the single action that settles it. The
 * shell renders the chat experience while `phase` is `Resolved`, a spinner
 * while `Loading`, and the blocked screen while `Blocked`.
 */
export function useAuth(): UseAuthResult {
  const [auth, setAuth] = useState<AuthState>(INITIAL_AUTH_STATE);

  const resolve = useCallback(
    (authEnforced: boolean, userInfo: UserInfo | null) => {
      if (userInfo) {
        // A signed-in user resolved: forward their object id everywhere.
        setUserId(userInfo.userId);
        setAuth({
          userId: userInfo.userId,
          userInfo,
          authEnforced,
          phase: AuthPhase.Resolved,
        });
        return;
      }
      if (authEnforced) {
        // Auth is enforced but no user resolved: block. Clear the
        // singleton back to the default; the shell makes no API calls.
        setUserId(null);
        setAuth({
          userId: DEFAULT_USER_ID,
          userInfo: null,
          authEnforced: true,
          phase: AuthPhase.Blocked,
        });
        return;
      }
      // Auth not enforced and no user: fall back to the default user.
      setUserId(null);
      setAuth({
        userId: DEFAULT_USER_ID,
        userInfo: null,
        authEnforced: false,
        phase: AuthPhase.Resolved,
      });
    },
    [],
  );

  return { auth, resolve };
}
