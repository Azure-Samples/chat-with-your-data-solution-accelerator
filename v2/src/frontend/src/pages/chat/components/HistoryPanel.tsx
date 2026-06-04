/**
 * Pillar: Scenario Pack
 * Phase: 4 (task #32) +
 *        6 (visual polish — icon buttons + hover-reveal actions,
 *           pulled forward for boss demo)
 *
 * Conversation history side panel. Loads `/api/history/conversations`
 * on mount, lets the user select / rename / delete entries. The
 * selected conversation id is bubbled up via `onSelect` so the chat
 * page can rehydrate messages once the SSE wiring (#24/#25) feeds
 * them through `ChatContext`.
 *
 * Backend agnostic: the router behind `/api/history` dispatches to
 * either `cosmosdb` or `postgresql` (see backend task #29) -- this
 * panel reads the discriminator from `/api/history/status` only to
 * surface it in the panel header for ops visibility, never to branch
 * behavior (Hard Rule #4: no `if/elif` over provider keys).
 *
 * Phase 6 polish: New / Rename / Delete buttons render as round icon
 * buttons (Fluent v9 Add16Regular / Edit16Regular / Delete16Regular).
 * Per-row Rename + Delete are hover/focus-revealed (Slack/Outlook
 * pattern). Every `data-testid` + `aria-label` is preserved verbatim
 * from Phase 4.
 *
 * Phase 4 MACAE re-skin: rows render as MACAE-style `.tab` chips
 * (border-radius var(--borderRadiusMedium), hover
 * var(--colorSubtleBackgroundHover), selected with a 2px
 * var(--colorCompoundBrandStroke) left tick). The outer landmark
 * (`<aside aria-label="conversation history">`) is now provided by
 * the parent `<PanelLeft>`, so this component renders a plain `<div>`
 * to avoid nesting two `complementary` landmarks.
 */
import { useCallback, useEffect, useState, type JSX } from "react";
import {
  Add16Regular,
  Delete16Regular,
  Edit16Regular,
} from "@fluentui/react-icons";
import type { HistoryConversation } from "@/models/chat";
import styles from "./HistoryPanel.module.css";

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";

interface HistoryStatus {
  enabled: boolean;
  db_type: string;
}

interface LoadState {
  status: "loading" | "ready" | "error";
  message?: string;
}

export interface HistoryPanelProps {
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}

function buildUrl(path: string): string {
  return `${BACKEND_URL.replace(/\/$/, "")}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (init?.headers !== undefined) {
    Object.assign(headers, init.headers as Record<string, string>);
  }
  const resp = await fetch(buildUrl(path), { ...init, headers });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  // 204 returns no body.
  if (resp.status === 204) {
    return undefined as unknown as T;
  }
  return (await resp.json()) as T;
}

export function HistoryPanel({
  selectedId,
  onSelect,
}: HistoryPanelProps): JSX.Element {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [status, setStatus] = useState<HistoryStatus | null>(null);
  const [items, setItems] = useState<HistoryConversation[]>([]);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const init: RequestInit = signal ? { signal } : {};
      const [statusPayload, list] = await Promise.all([
        fetchJson<HistoryStatus>("/api/history/status", init),
        fetchJson<HistoryConversation[]>("/api/history/conversations", init),
      ]);
      if (signal?.aborted) {
        return;
      }
      setStatus(statusPayload);
      setItems(list);
      setLoad({ status: "ready" });
    } catch (err) {
      if (
        err instanceof DOMException &&
        err.name === "AbortError"
      ) {
        return;
      }
      const message = err instanceof Error ? err.message : "load failed";
      setLoad({ status: "error", message });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => {
      controller.abort();
    };
  }, [refresh]);

  const handleNew = useCallback(async () => {
    try {
      const created = await fetchJson<HistoryConversation>(
        "/api/history/conversations",
        { method: "POST", body: JSON.stringify({ title: "New chat" }) },
      );
      setItems((prev) => [created, ...prev]);
      onSelect?.(created.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "create failed";
      setLoad({ status: "error", message });
    }
  }, [onSelect]);

  const handleRename = useCallback(
    async (id: string, currentTitle: string) => {
      // `prompt` keeps this unit self-contained -- a richer modal
      // lands when the panel grows beyond Phase 4.
      const next = window.prompt("Rename conversation", currentTitle);
      if (next === null || next.trim() === "") {
        return;
      }
      try {
        const updated = await fetchJson<HistoryConversation>(
          `/api/history/conversations/${encodeURIComponent(id)}`,
          { method: "PATCH", body: JSON.stringify({ title: next.trim() }) },
        );
        setItems((prev) =>
          prev.map((c) => (c.id === id ? { ...c, ...updated } : c)),
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "rename failed";
        setLoad({ status: "error", message });
      }
    },
    [],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm("Delete this conversation?")) {
        return;
      }
      try {
        await fetchJson<null>(
          `/api/history/conversations/${encodeURIComponent(id)}`,
          { method: "DELETE" },
        );
        setItems((prev) => prev.filter((c) => c.id !== id));
      } catch (err) {
        const message = err instanceof Error ? err.message : "delete failed";
        setLoad({ status: "error", message });
      }
    },
    [],
  );

  return (
    <div
      data-testid="history-panel"
      className={styles.panel}
    >
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <h3 className={styles.title}>History</h3>
          <button
            type="button"
            onClick={() => {
              void handleNew();
            }}
            data-testid="history-new"
            aria-label="New chat"
            title="New chat"
            className={styles.iconButton}
          >
            <Add16Regular aria-hidden="true" />
          </button>
        </div>
        {status !== null && (
          <p data-testid="history-db-type" className={styles.dbType}>
            backend: {status.db_type}
          </p>
        )}
      </header>

      {load.status === "loading" && (
        <p data-testid="history-loading" className={styles.note}>
          Loading conversations…
        </p>
      )}
      {load.status === "error" && (
        <p data-testid="history-error" role="alert" className={styles.error}>
          Could not load history: {load.message}
        </p>
      )}
      {load.status === "ready" && items.length === 0 && (
        <p data-testid="history-empty" className={styles.note}>
          No conversations yet.
        </p>
      )}
      {load.status === "ready" && items.length > 0 && (
        <ul data-testid="history-list" className={styles.list}>
          {items.map((c) => {
            const isSelected = c.id === selectedId;
            return (
              <li
                key={c.id}
                data-testid={`history-item-${c.id}`}
                aria-current={isSelected ? "true" : undefined}
                className={styles.item}
                data-selected={isSelected ? "true" : "false"}
              >
                <button
                  type="button"
                  onClick={() => onSelect?.(c.id)}
                  data-testid={`history-select-${c.id}`}
                  className={styles.selectButton}
                  title={c.title || "Untitled"}
                >
                  {c.title || "Untitled"}
                </button>
                <div className={styles.actions}>
                  <button
                    type="button"
                    onClick={() => {
                      void handleRename(c.id, c.title);
                    }}
                    data-testid={`history-rename-${c.id}`}
                    aria-label={`Rename ${c.title || "Untitled"}`}
                    title="Rename"
                    className={styles.iconButton}
                  >
                    <Edit16Regular aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleDelete(c.id);
                    }}
                    data-testid={`history-delete-${c.id}`}
                    aria-label={`Delete ${c.title || "Untitled"}`}
                    title="Delete"
                    className={styles.iconButton}
                  >
                    <Delete16Regular aria-hidden="true" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
