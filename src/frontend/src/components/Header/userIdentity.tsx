/**
 * Display-name + initials helpers for the header user badge. Kept in a
 * non-component module so <HeaderTools> exports only its component
 * (React Fast Refresh requires component-only exports).
 *
 * Initials derivation mirrors the reference architecture's login-button
 * pattern (`getUserInitials`). The display name is read from the Easy Auth
 * claims resolved into `UserInfo`.
 */
import type { UserInfo } from "@/models/auth";

const GUEST_NAME = "Guest";

// Easy Auth claim types carrying a human display name, in preference
// order: `name` is the AAD display name ("John Doe"); the rest are
// fallbacks so a signed-in user without a `name` claim still gets a
// meaningful initial.
const DISPLAY_NAME_CLAIM_TYPES = [
  "name",
  "preferred_username",
  "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
  "emails",
];

/**
 * Resolve a display name from the signed-in user's claims, or "Guest"
 * when no user is signed in (or no name-bearing claim is present).
 */
export function resolveDisplayName(
  userInfo: UserInfo | null | undefined,
): string {
  if (userInfo === null || userInfo === undefined) {
    return GUEST_NAME;
  }
  for (const claimType of DISPLAY_NAME_CLAIM_TYPES) {
    const value = userInfo.claims
      .find((claim) => claim.typ === claimType)
      ?.val.trim();
    if (value !== undefined && value !== "") {
      return value;
    }
  }
  return userInfo.userId || GUEST_NAME;
}

/**
 * Up-to-two-letter initials from a display name (mirrors the reference
 * architecture's `getUserInitials`): first letters of the first two whitespace parts,
 * else the first letter of a single-part name; parenthetical segments
 * are stripped first. Returns "G" for an empty name.
 */
export function userInitials(name: string): string {
  const cleaned = name.replace(/\s*\([^)]*\)/g, "").trim();
  if (cleaned === "") {
    return "G";
  }
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    const first = parts[0]?.charAt(0) ?? "";
    const second = parts[1]?.charAt(0) ?? "";
    return (first + second).toUpperCase();
  }
  return cleaned.charAt(0).toUpperCase();
}
