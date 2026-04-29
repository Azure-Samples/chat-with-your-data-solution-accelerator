/**
 * Pillar: Scenario Pack
 * Phase: 4 (task #32)
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
 */
import { useCallback, useEffect, useState, type JSX } from "react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "";

export interface HistoryConversation {
  id: string;
  title: string;
  updated_at: string;
}

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
  const resp = await fetch(buildUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
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
      const [statusPayload, list] = await Promise.all([
        fetchJson<HistoryStatus>("/api/history/status", { signal }),
        fetchJson<HistoryConversation[]>("/api/history/conversations", {
          signal,
        }),
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
    refresh(controller.signal);
    return () => controller.abort();
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
        await fetchJson<void>(
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
    <aside aria-label="conversation history" data-testid="history-panel">
      <header>
        <h3>History</h3>
        {status !== null && (
          <p data-testid="history-db-type">backend: {status.db_type}</p>
        )}
        <button type="button" onClick={handleNew} data-testid="history-new">
          New chat
        </button>
      </header>

      {load.status === "loading" && (
        <p data-testid="history-loading">Loading conversations…</p>
      )}
      {load.status === "error" && (
        <p data-testid="history-error" role="alert">
          Could not load history: {load.message}
        </p>
      )}
      {load.status === "ready" && items.length === 0 && (
        <p data-testid="history-empty">No conversations yet.</p>
      )}
      {load.status === "ready" && items.length > 0 && (
        <ul data-testid="history-list">
          {items.map((c) => {
            const isSelected = c.id === selectedId;
            return (
              <li
                key={c.id}
                data-testid={`history-item-${c.id}`}
                aria-current={isSelected ? "true" : undefined}
              >
                <button
                  type="button"
                  onClick={() => onSelect?.(c.id)}
                  data-testid={`history-select-${c.id}`}
                >
                  {c.title || "Untitled"}
                </button>
                <button
                  type="button"
                  onClick={() => handleRename(c.id, c.title)}
                  data-testid={`history-rename-${c.id}`}
                  aria-label={`Rename ${c.title || "Untitled"}`}
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(c.id)}
                  data-testid={`history-delete-${c.id}`}
                  aria-label={`Delete ${c.title || "Untitled"}`}
                >
                  Delete
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
