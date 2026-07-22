/**
 * Conversation history side panel. Loads `/api/history/conversations`
 * on mount, lets the user select / rename / delete entries. The
 * selected conversation id is bubbled up via `onSelect` so the chat
 * page can rehydrate messages once the SSE wiring feeds them through
 * `ChatContext`.
 *
 * Backend agnostic: the `/api/history` router dispatches to either
 * `cosmosdb` or `postgresql`, but this panel never reads or surfaces
 * that discriminator and never branches on it (Hard Rule #4: no
 * `if/elif` over provider keys).
 *
 * Rename / Delete buttons render as round icon buttons (Fluent v9
 * Edit16Regular / Delete16Regular). Per-row Rename + Delete are
 * hover/focus-revealed (Slack/Outlook pattern).
 *
 * Rows render as `.tab` chips (border-radius var(--borderRadiusMedium),
 * hover var(--colorSubtleBackgroundHover), selected with a 2px
 * var(--colorCompoundBrandStroke) left tick). The outer landmark
 * (`<aside aria-label="conversation history">`) is provided by the
 * parent `<PanelLeft>`, so this component renders a plain `<div>` to
 * avoid nesting two `complementary` landmarks.
 */
import { useCallback, useEffect, useState, type JSX } from "react";
import { Delete16Regular, Edit16Regular } from "@fluentui/react-icons";
import type { HistoryConversation } from "@/models/chat";
import { userIdHeaders } from "@/api/auth";
import { getBackendUrl, loadRuntimeConfig } from "@/api/runtimeConfig";
import styles from "./HistoryPanel.module.css";

interface LoadState {
  status: "loading" | "ready" | "error";
  message?: string;
}

export interface HistoryPanelProps {
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  // Bumping this value triggers a silent background re-fetch of the
  // conversation list (e.g. when the chat page mints a brand-new
  // conversation, so the freshly-persisted entry appears in the panel).
  reloadKey?: number;
}

function buildUrl(path: string): string {
  return `${getBackendUrl().replace(/\/$/, "")}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...userIdHeaders(),
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
  reloadKey = 0,
}: HistoryPanelProps): JSX.Element {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [items, setItems] = useState<HistoryConversation[]>([]);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      await loadRuntimeConfig();
      if (signal?.aborted) {
        return;
      }
      const init: RequestInit = signal ? { signal } : {};
      const list = await fetchJson<HistoryConversation[]>(
        "/api/history/conversations",
        init,
      );
      if (signal?.aborted) {
        return;
      }
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
  }, [refresh, reloadKey]);

  const handleRename = useCallback(
    async (id: string, currentTitle: string) => {
      // `prompt` keeps this rename flow self-contained.
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
    async (id: string, title: string) => {
      const label = title || "Untitled";
      if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) {
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
        </div>
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
                      void handleDelete(c.id, c.title);
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
