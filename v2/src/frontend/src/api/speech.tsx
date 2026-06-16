/**
 * Pillar: Stable Core
 * Phase: 4 (S1 / SPEECH-MVP — pulled forward from Phase 5 task #38)
 *
 * REST client for `GET /api/speech`. Mirrors the hand-rolled
 * `streamChat.ts` pattern — no OpenAPI generator wired in v2 yet, so
 * the FE keeps a thin typed fetch wrapper per endpoint and pays the
 * tiny duplication cost in exchange for zero generator setup.
 *
 * The backend mints a 10-minute Azure Speech authorization token via
 * AAD (Hard Rule #2 — no subscription keys ever cross the wire). The
 * browser SDK consumes the token via
 * `SpeechConfig.fromAuthorizationToken(token, region)` and talks to
 * Azure Speech directly; no audio ever flows back through this
 * backend.
 */
import { userIdHeaders } from "@/api/auth";
import type { SpeechConfigPayload } from "@/models/speech";

const SPEECH_URL = "/api/speech";

/**
 * Fetch a fresh Speech SDK bootstrap payload from the backend.
 *
 * @throws Error when the response status is not 2xx (503 means the
 * backend has no Speech account configured; 502 means the AAD or
 * issueToken call failed). Caller decides how to surface — the
 * `useSpeechRecognition` hook turns these into a typed `error` state
 * so the mic button can be disabled gracefully.
 */
export async function getSpeechConfig(): Promise<SpeechConfigPayload> {
  const response = await fetch(SPEECH_URL, {
    method: "GET",
    headers: { Accept: "application/json", ...userIdHeaders() },
  });
  if (!response.ok) {
    throw new Error(
      `getSpeechConfig: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as SpeechConfigPayload;
  return body;
}
