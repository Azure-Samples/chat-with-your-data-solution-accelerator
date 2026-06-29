/**
 * Pillar: Stable Core
 * Phase: 5 (frontend — user identity)
 *
 * Vitest suite for the `useAuth` shell state machine. Drives the hook
 * through its `resolve(...)` action and asserts both the React state
 * transitions and the side effect on the `api/auth.tsx` resolved-id
 * singleton (so header forwarding picks up the right principal).
 */
import { afterEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useAuth } from "@/hooks/useAuth";
import { DEFAULT_USER_ID, getUserId, setUserId } from "@/api/auth";
import { AuthPhase, type UserInfo } from "@/models/auth";

const RESOLVED_OID = "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab";

const RESOLVED_USER: UserInfo = {
  userId: RESOLVED_OID,
  claims: [
    {
      typ: "http://schemas.microsoft.com/identity/claims/objectidentifier",
      val: RESOLVED_OID,
    },
  ],
};

describe("useAuth", () => {
  afterEach(() => {
    // The hook mutates the shared auth singleton; reset it between tests.
    setUserId(null);
  });

  it("starts in the loading phase on the default user", () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current.auth).toEqual({
      userId: DEFAULT_USER_ID,
      userInfo: null,
      phase: AuthPhase.Loading,
    });
  });

  it("resolves to the signed-in user and forwards their id", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.resolve(RESOLVED_USER);
    });

    expect(result.current.auth).toEqual({
      userId: RESOLVED_OID,
      userInfo: RESOLVED_USER,
      phase: AuthPhase.Resolved,
    });
    expect(getUserId()).toBe(RESOLVED_OID);
  });

  it("falls back to the default user when no principal resolves", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.resolve(null);
    });

    expect(result.current.auth).toEqual({
      userId: DEFAULT_USER_ID,
      userInfo: null,
      phase: AuthPhase.Resolved,
    });
    expect(getUserId()).toBe(DEFAULT_USER_ID);
  });

  it("keeps a stable resolve identity across renders", () => {
    const { result, rerender } = renderHook(() => useAuth());

    const firstResolve = result.current.resolve;
    rerender();

    expect(result.current.resolve).toBe(firstResolve);
  });
});
