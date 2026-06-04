/**
 * Pillar: Stable Core
 * Phase: 1 +
 *        6 (visual polish — header + theme + history toggle, pulled forward for boss demo) +
 *        4 (MACAE re-skin — Fluent UI v9 provider via FluentThemeBridge) +
 *        7 (Testing + Documentation — admin Delete data routing)
 *
 * App shell. Pings `/api/health` against the configured backend (so
 * docker compose can verify `VITE_BACKEND_URL` wiring) and mounts the
 * chat page or one of the admin pages (Ingest data / Delete data)
 * depending on the active `view`. Admin nav visibility is driven by
 * a one-shot `getAdminStatus()` probe on mount: a 2xx response
 * surfaces the Admin links in the header, any non-2xx (or transport
 * failure) keeps them hidden so non-admin sessions never see a
 * dead-end link.
 *
 * Phase-6 polish wraps the tree in a `<ThemeProvider>` and renders the
 * Coral `<Header>` that owns the light/dark toggle, the
 * history-panel toggle, and (when wired) the primary nav. State for
 * `historyOpen`, `view`, and `adminAvailable` lives here so a single
 * source of truth feeds both header and the routed view.
 *
 * MACAE re-skin (S2): a `<FluentThemeBridge>` lives between
 * `<ThemeProvider>` and the rest of the tree so every Fluent UI v9
 * component inherits `teamsLightTheme` / `teamsDarkTheme` driven by
 * our own theme state. The visual shell uses `<CoralShellColumn>` (the
 * full-viewport vertical stack hosting the `<Header>`) and
 * `<CoralShellRow>` (the horizontal sidebar+content split) so the
 * layout matches MACAE's recessed-shell-with-raised-panels pattern.
 */
import { useState, useEffect, type JSX } from "react";
import { Header, type AppView } from "./components/Header/Header";
import { CoralShellColumn } from "./components/CoralShell/CoralShellColumn";
import { CoralShellRow } from "./components/CoralShell/CoralShellRow";
import { ChatPage } from "./pages/chat/ChatPage";
import { IngestData } from "./pages/admin/IngestData/IngestData";
import { DeleteData } from "./pages/admin/DeleteData/DeleteData";
import { Configuration } from "./pages/admin/Configuration/Configuration";
import { PromptEditor } from "./pages/admin/PromptEditor/PromptEditor";
import { getAdminStatus } from "./api/admin";
import { Section } from "./models/sections";
import { FluentThemeBridge } from "./theme/FluentThemeBridge";
import { ThemeProvider } from "./theme/themeContext";
import "./theme/tokens.css";

type HealthState =
  | { status: "loading" }
  | { status: "ok"; payload: unknown }
  | { status: "error"; message: string };

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";

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
  const [view, setView] = useState<AppView>(Section.Chat);
  // `null` = probe in-flight; `true`/`false` = settled. Tri-state lets
  // the header render its nav slot synchronously while keeping the
  // Admin button hidden until the probe resolves.
  const [adminAvailable, setAdminAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchHealth(controller.signal).then((next) => {
      // Suppress the placeholder loading state set by AbortError so
      // the user doesn't see an indefinite spinner after unmount.
      if (!controller.signal.aborted) {
        setHealth(next);
      }
    });
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getAdminStatus()
      .then(() => {
        if (!cancelled) {
          setAdminAvailable(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdminAvailable(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ThemeProvider>
      <FluentThemeBridge>
        <CoralShellColumn>
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
          <Header
            title="Chat with your data"
            historyOpen={historyOpen}
            onToggleHistory={() => {
              setHistoryOpen((v) => !v);
            }}
            onNewChat={() => {
              setNewChatNonce((n) => n + 1);
            }}
            view={view}
            onSelectView={setView}
            adminAvailable={adminAvailable}
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
            {health.status === "loading" && (
              <p data-testid="health">Checking…</p>
            )}
            {health.status === "ok" && (
              <p data-testid="health">Connected to backend.</p>
            )}
            {health.status === "error" && (
              <p data-testid="health" role="alert">
                Cannot reach backend: {health.message}
              </p>
            )}
          </section>
          <CoralShellRow>
            {view === Section.Chat && (
              <ChatPage key={newChatNonce} historyOpen={historyOpen} />
            )}
            {view === Section.AdminIngest && <IngestData />}
            {view === Section.AdminDelete && <DeleteData />}
            {view === Section.AdminConfig && <Configuration />}
            {view === Section.AdminPrompt && <PromptEditor />}
          </CoralShellRow>
        </CoralShellColumn>
      </FluentThemeBridge>
    </ThemeProvider>
  );
}
