/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * REST client for the per-message feedback endpoint backing the
 * thumbs-up / thumbs-down + reason picker rendered per assistant
 * message in `<FeedbackButtons>`. Mirrors the hand-rolled
 * `admin.ts` pattern — one typed fetch wrapper per endpoint, no
 * generated OpenAPI client wired in v2 yet.
 *
 * Backend surface: `POST /api/history/messages/{message_id}/feedback`
 * with body `{"feedback": <string, 1-64 chars>}`. The endpoint
 * returns `204 No Content` on success and `404` if the message id
 * is unknown. The `feedback` field is intentionally freeform on
 * the backend so UI variants (positive / negative / structured
 * payloads) can ship without a schema migration.
 */

/**
 * Submit a feedback string for a single assistant message.
 *
 * @param messageId - the message id from `MessageRecord.id` /
 *   `ChatMessage.id`. Passed through `encodeURIComponent` so an
 *   accidentally unsafe id never escapes the path segment.
 * @param feedback - the feedback value to persist. Backend
 *   enforces 1–64 chars. Common values: `"positive"` /
 *   `"negative"`; richer reason-picker payloads are permitted.
 *
 * @throws Error when the response status is not 2xx. Callers
 *   should distinguish: 404 (message id unknown — likely a stale
 *   client state, e.g. mid-stream message id), 401/403 (auth),
 *   422 (backend rejected the feedback value as too long or
 *   empty), 5xx (backend down).
 */
export async function setFeedback(
  messageId: string,
  feedback: string,
): Promise<void> {
  const url = `/api/history/messages/${encodeURIComponent(messageId)}/feedback`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
  if (!response.ok) {
    throw new Error(
      `setFeedback: request failed with status ${response.status}`,
    );
  }
}
