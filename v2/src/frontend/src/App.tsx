/**
 * Pillar: Stable Core
 * Phase: 1 (App shell)
 *
 * Router-driven app shell. `App` provides the theme + Fluent UI v9
 * bridge and a `<BrowserRouter>`; `AppShell` derives the active page
 * from the URL and drives navigation through the `<Header>` nav.
 * Browser routes: `/` -> chat; `/admin` -> the `<AdminLayout>` shell
 * wrapping the `ingest|delete|config|prompt` pages (bare `/admin`
 * redirects to `ingest`); any other path -> redirect to `/`.
 *
 * On mount `AppShell` pings `/api/health` (so docker compose can verify
 * `VITE_BACKEND_URL` wiring) and runs a one-shot `getAdminStatus()`
 * probe: a 2xx surfaces the Admin nav links, any non-2xx (or transport
 * failure) keeps them hidden so non-admin sessions never see a
 * dead-end link. `historyOpen`, `newChatNonce`, and `adminAvailable`
 * live here as the single source of truth feeding both the header and
 * the routed view; the active section is derived from the URL via
 * `pathToSection`.
 */
import { useState, useEffect, type JSX } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Header } from "./components/Header/Header";
import { CoralShellColumn } from "./components/CoralShell/CoralShellColumn";
import { CoralShellRow } from "./components/CoralShell/CoralShellRow";
import { ChatPage } from "./pages/chat/ChatPage";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { IngestData } from "./pages/admin/IngestData/IngestData";
import { DeleteData } from "./pages/admin/DeleteData/DeleteData";
import { Configuration } from "./pages/admin/Configuration/Configuration";
import { PromptEditor } from "./pages/admin/PromptEditor/PromptEditor";
import { getAdminStatus } from "./api/admin";
import { Section, SectionPath, pathToSection } from "./models/sections";
import { FluentThemeBridge } from "./theme/FluentThemeBridge";
import { ThemeProvider } from "./theme/themeContext";
import "./theme/tokens.css";

type HealthState =
  | { status: "loading" }
  | { status: "ok"; payload: unknown }
  | { status: "error"; message: string };

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";

/** Parent route the admin pages nest under (see <AdminLayout>). */
const ADMIN_BASE_PATH = "/admin";

/** Trailing segment of an admin `SectionPath` for its nested <Route>. */
function adminChildPath(section: Section): string {
  return SectionPath[section].slice(ADMIN_BASE_PATH.length + 1);
}

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

function AppShell(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const view = pathToSection(location.pathname);
  const [health, setHealth] = useState<HealthState>({ status: "loading" });
  const [historyOpen, setHistoryOpen] = useState(false);
  // Bump this counter to force a fresh <ChatPage> mount, which resets
  // ChatProvider state + selectedId without threading dispatch through
  // the App shell (avoids lifting ChatProvider up a layer, which would
  // be a structural change).
  const [newChatNonce, setNewChatNonce] = useState(0);
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
        onSelectView={(next) => {
          void navigate(SectionPath[next]);
        }}
        adminAvailable={adminAvailable}
        onOpenAdmin={() => {
          void navigate(SectionPath[Section.AdminIngest]);
        }}
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
        <Routes>
          <Route
            path={SectionPath[Section.Chat]}
            element={<ChatPage key={newChatNonce} historyOpen={historyOpen} />}
          />
          <Route path={ADMIN_BASE_PATH} element={<AdminLayout />}>
            <Route
              index
              element={
                <Navigate to={adminChildPath(Section.AdminIngest)} replace />
              }
            />
            <Route
              path={adminChildPath(Section.AdminIngest)}
              element={<IngestData />}
            />
            <Route
              path={adminChildPath(Section.AdminDelete)}
              element={<DeleteData />}
            />
            <Route
              path={adminChildPath(Section.AdminConfig)}
              element={<Configuration />}
            />
            <Route
              path={adminChildPath(Section.AdminPrompt)}
              element={<PromptEditor />}
            />
          </Route>
          <Route
            path="*"
            element={<Navigate to={SectionPath[Section.Chat]} replace />}
          />
        </Routes>
      </CoralShellRow>
    </CoralShellColumn>
  );
}

export function App(): JSX.Element {
  return (
    <ThemeProvider>
      <FluentThemeBridge>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </FluentThemeBridge>
    </ThemeProvider>
  );
}
