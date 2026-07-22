/**
 * Vitest shape + enum assertions for the auth model. Runtime `expect`
 * checks confirm the `AuthPhase` closed set and the interface field
 * types reach the FE intact; `expectTypeOf` breaks the build on drift.
 */
import { describe, expect, expectTypeOf, it } from "vitest";
import { AuthPhase } from "@/models/auth";
import type {
  AuthMeResponse,
  AuthState,
  UserClaim,
  UserInfo,
} from "@/models/auth";

describe("AuthPhase enum", () => {
  it("maps every member to its canonical string", () => {
    expect(AuthPhase.Loading).toBe("loading");
    expect(AuthPhase.Resolved).toBe("resolved");
  });

  it("exposes the full closed phase set via Object.values", () => {
    expect([...Object.values(AuthPhase)].sort()).toEqual([
      "loading",
      "resolved",
    ]);
  });

  it("is read-only at the type layer (`as const`)", () => {
    // @ts-expect-error -- `as const` maps must be readonly at compile time.
    AuthPhase.Loading = "mutated";
  });

  it("produces a literal-union type covering every phase string", () => {
    expectTypeOf<AuthPhase>().toEqualTypeOf<"loading" | "resolved">();
  });
});

describe("auth wire + domain shapes", () => {
  it("accepts the external /.auth/me principal shape (snake_case)", () => {
    const claim: UserClaim = {
      typ: "http://schemas.microsoft.com/identity/claims/objectidentifier",
      val: "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
    };
    const principal: AuthMeResponse = {
      user_id: "user@contoso.example.com",
      user_claims: [claim],
      provider_name: "aad",
    };
    expect(principal.user_claims[0]?.typ).toMatch(/objectidentifier$/);
    expect(principal.user_claims[0]?.val).toBe(
      "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
    );
    expect(principal.provider_name).toBe("aad");
  });

  it("accepts the FE-owned resolved UserInfo shape", () => {
    const info: UserInfo = {
      userId: "6b2e1f54-1c2d-4a8b-9f0e-1234567890ab",
      claims: [],
    };
    expect(info.userId).toBe("6b2e1f54-1c2d-4a8b-9f0e-1234567890ab");
    expect(info.claims).toEqual([]);
  });

  it("models the auth store state with a closed-set phase", () => {
    const state: AuthState = {
      userId: "00000000-0000-0000-0000-000000000000",
      userInfo: null,
      phase: AuthPhase.Resolved,
    };
    expect(state.userId).toBe("00000000-0000-0000-0000-000000000000");
    expect(state.userInfo).toBeNull();
    expect(state.phase).toBe("resolved");
  });
});
