/**
 * Pillar: Stable Core
 * Phase: 1 +
 *        6 (visual polish — header + theme + history toggle, pulled forward for boss demo)
 *
 * App shell. Pings `/api/health` against the configured backend (so
 * docker compose can verify `VITE_BACKEND_URL` wiring) and mounts
 * the chat page from dev_plan #15. SSE wiring lands in #24; routing
 * lands with the admin merge in #36. Phase-6 polish wraps the tree in
 * a `<ThemeProvider>` and renders an `<AppHeader>` that owns the
 * light/dark toggle and the history-panel toggle (state lives here so
 * a single source of truth feeds both header and `<ChatPage>`).
 */
import { useState, useEffect, type JSX } from "react";
import { AppHeader } from "./components/AppHeader/AppHeader";
import { ChatPage } from "./pages/chat/ChatPage";
import { ThemeProvider } from "./theme/themeContext";
import "./theme/tokens.css";

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
  const [historyOpen, setHistoryOpen] = useState(false);
  // Bump this counter to force a fresh <ChatPage> mount, which resets
  // ChatProvider state + selectedId without threading dispatch through
  // the App shell (avoids lifting ChatProvider up a layer, which would
  // be a structural change).
  const [newChatNonce, setNewChatNonce] = useState(0);

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
    <ThemeProvider>
      <h1
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        CWYD v2
      </h1>
      <AppHeader
        title="Chat with your data"
        historyOpen={historyOpen}
        onToggleHistory={() => setHistoryOpen((v) => !v)}
        onNewChat={() => setNewChatNonce((n) => n + 1)}
      />
      <section
        aria-label="backend health"
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
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
      <ChatPage key={newChatNonce} historyOpen={historyOpen} />
    </ThemeProvider>
  );
}
