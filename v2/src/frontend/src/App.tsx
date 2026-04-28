/**
 * Pillar: Stable Core
 * Phase: 1
 *
 * App shell. Pings `/api/health` against the configured backend (so
 * docker compose can verify `VITE_BACKEND_URL` wiring) and mounts
 * the chat page from dev_plan #15. SSE wiring lands in #24; routing
 * lands with the admin merge in #36.
 */
import { useEffect, useState } from "react";
import { ChatPage } from "./pages/chat/ChatPage";

type HealthState =
  | { status: "loading" }
  | { status: "ok"; payload: unknown }
  | { status: "error"; message: string };

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "";

async function fetchHealth(signal: AbortSignal): Promise<HealthState> {
  const url = `${BACKEND_URL.replace(/\/$/, "")}/api/health`;
  try {
    const response = await fetch(url, { signal });
    if (!response.ok) {
      return { status: "error", message: `HTTP ${response.status}` };
    }
    const payload: unknown = await response.json();
    return { status: "ok", payload };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      // Component unmounted while in-flight; treat as still loading
      // so React Strict Mode's double-invoke doesn't surface a fake
      // error in the UI.
      return { status: "loading" };
    }
    const message =
      err instanceof Error ? err.message : "Unknown fetch failure";
    return { status: "error", message };
  }
}

export function App(): JSX.Element {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal).then((next) => {
      // Suppress the placeholder loading state set by AbortError so
      // the user doesn't see an indefinite spinner after unmount.
      if (!controller.signal.aborted) {
        setHealth(next);
      }
    });
    return () => controller.abort();
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>CWYD v2</h1>
      <section aria-label="backend health">
        <h2>Backend health</h2>
        {health.status === "loading" && <p data-testid="health">Checking…</p>}
        {health.status === "ok" && (
          <p data-testid="health">Connected to backend.</p>
        )}
        {health.status === "error" && (
          <p data-testid="health" role="alert">
            Cannot reach backend: {health.message}
          </p>
        )}
      </section>
      <ChatPage />
    </main>
  );
}
