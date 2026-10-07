/**
 * Browser-side MSAL (PKCE) seam. The deployed SPA runs an interactive
 * authorization-code + PKCE flow directly against Microsoft Entra -- a
 * public client with no secret, matching the solution's secretless
 * managed-identity posture. The resolved backend access token and the
 * signed-in user's object id feed the existing module singletons in
 * `api/auth.tsx` (`setAccessToken` / `setUserId`), so every REST client
 * keeps forwarding `Authorization` + `x-ms-client-principal-id` unchanged.
 *
 * The seam splits into a pure config mapping (`buildMsalConfig`), a
 * lazily-initialised app singleton (`getMsalApp`), and the interactive
 * resolution step (`resolveAuthWith`) that the app bootstrap drives.
 */
import {
  PublicClientApplication,
  type AccountInfo,
  type AuthenticationResult,
  type Configuration,
  type IPublicClientApplication,
} from "@azure/msal-browser";

import type { AuthRuntimeConfig } from "@/api/runtimeConfig";
import type { UserClaim } from "@/models/auth";

/** The signed-in identity + backend bearer resolved from Entra. */
export interface ResolvedAuth {
  userId: string;
  accessToken: string;
  claims: UserClaim[];
}

/**
 * Map the runtime auth config onto an MSAL `Configuration`, or `null`
 * when no client id is configured (local dev / no identity provider).
 * `sessionStorage` keeps tokens out of durable storage; the redirect URI
 * is the SPA's own origin, which must be registered as a SPA redirect on
 * the app registration.
 */
export function buildMsalConfig(config: AuthRuntimeConfig): Configuration | null {
  if (!config.clientId || !config.authority) {
    return null;
  }
  return {
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      redirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: "sessionStorage",
    },
  };
}

let appSingleton: IPublicClientApplication | null = null;

/**
 * Lazily build and initialise the MSAL app singleton. Returns `null`
 * when no identity provider is configured, so the bootstrap falls back
 * to the anonymous default user. MSAL v4 requires an explicit
 * `initialize()` before any interactive call.
 */
export async function getMsalApp(
  config: AuthRuntimeConfig,
): Promise<IPublicClientApplication | null> {
  if (appSingleton) {
    return appSingleton;
  }
  const msalConfig = buildMsalConfig(config);
  if (!msalConfig) {
    return null;
  }
  const app = new PublicClientApplication(msalConfig);
  await app.initialize();
  appSingleton = app;
  return app;
}

/** Flatten MSAL `idTokenClaims` into the FE-owned `UserClaim[]` shape. */
function toClaims(account: AccountInfo): UserClaim[] {
  const raw = account.idTokenClaims ?? {};
  return Object.entries(raw).map(([typ, val]) => ({
    typ,
    val: typeof val === "string" ? val : JSON.stringify(val),
  }));
}

/** Map a completed token result onto the FE-owned `ResolvedAuth`. */
function toResolvedAuth(result: AuthenticationResult): ResolvedAuth {
  const account = result.account;
  const oid =
    typeof account.idTokenClaims?.oid === "string"
      ? account.idTokenClaims.oid
      : account.localAccountId;
  return {
    userId: oid,
    // Forward the ID token: its audience is the app registration client
    // id, which the backend Easy Auth is configured to accept. No custom
    // API scope or backend audience change is required.
    accessToken: result.idToken,
    claims: toClaims(account),
  };
}

/**
 * Resolve the signed-in user and an ID token the backend accepts. Picks
 * up a redirect result, then an existing account; with none it starts a
 * login redirect and returns `null` (the page is navigating away). With
 * an account it acquires the token silently, falling back to an
 * interactive redirect on `InteractionRequired` -- again returning
 * `null` while the browser redirects.
 */
export async function resolveAuthWith(
  app: IPublicClientApplication,
  scopes: string[],
): Promise<ResolvedAuth | null> {
  const redirectResult = await app.handleRedirectPromise();
  const account: AccountInfo | null =
    redirectResult?.account ??
    app.getActiveAccount() ??
    app.getAllAccounts()[0] ??
    null;

  if (!account) {
    await app.loginRedirect({ scopes });
    return null;
  }

  app.setActiveAccount(account);
  try {
    const result = await app.acquireTokenSilent({ account, scopes });
    return toResolvedAuth(result);
  } catch {
    await app.acquireTokenRedirect({ account, scopes });
    return null;
  }
}

/** Clear the app singleton. Test-only seam for isolation between cases. */
export function resetMsalApp(): void {
  appSingleton = null;
}
