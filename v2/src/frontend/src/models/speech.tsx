/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Wire shapes for the `/api/speech` REST surface. The backend mints
 * a short-lived Azure Speech authorization token via AAD; this is the
 * payload the browser SDK consumes via
 * `SpeechConfig.fromAuthorizationToken(token, region)`. Mirrors the
 * shape returned by `backend.routers.speech.get_speech_config`.
 */

export interface SpeechConfigPayload {
  token: string;
  region: string;
  languages: string[];
}
