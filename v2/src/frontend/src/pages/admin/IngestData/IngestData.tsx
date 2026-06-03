/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Admin "Ingest Data" page. Three independent sections share one
 * `useReducer` so per-entry status (pending / uploading / success /
 * failed) survives across re-renders without leaking into global app
 * state:
 *
 * 1. **File upload** -- drag-drop zone + browse button. Accepts
 *    `.pdf,.docx,.txt`; rejects anything larger than 50 MiB or with
 *    an unsupported extension before touching the wire. Failed
 *    entries expose a Retry button that re-fires the same `File`.
 * 2. **Add URL** -- single-line text input. The URL must parse via
 *    `new URL(...)` before submission; submitted entries surface the
 *    server-stamped `ingestion_job_id` and `document_count`.
 * 3. **Reprocess all** -- prominent destructive action gated by a
 *    typed-confirmation modal (operator must type `REPROCESS`
 *    verbatim) so a stray click never re-fans the entire documents
 *    container onto the queue.
 *
 * All three sections route through `src/api/admin.tsx`, never
 * `fetch` directly -- the page is wire-shape-agnostic.
 */
import {
  useCallback,
  useReducer,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type JSX,
} from "react";
import { Button, Input } from "@fluentui/react-components";
import {
  addDocumentUrl,
  reprocessAll,
  uploadDocument,
} from "../../../api/admin";
import type {
  IngestUrlResponse,
  ReprocessResponse,
  UploadResponse,
} from "../../../models/admin";
import styles from "./IngestData.module.css";

export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;
export const REPROCESS_CONFIRM_TOKEN = "REPROCESS";

type UploadStatus = "pending" | "uploading" | "success" | "failed";
type UrlStatus = "pending" | "submitting" | "success" | "failed";
type ReprocessStatus =
  | "idle"
  | "confirming"
  | "running"
  | "success"
  | "failed";

interface UploadEntry {
  id: string;
  file: File;
  status: UploadStatus;
  error?: string;
  response?: UploadResponse;
}

interface UrlEntry {
  id: string;
  url: string;
  status: UrlStatus;
  error?: string;
  response?: IngestUrlResponse;
}

interface ReprocessState {
  status: ReprocessStatus;
  error?: string;
  response?: ReprocessResponse;
}

interface IngestDataState {
  uploads: UploadEntry[];
  urls: UrlEntry[];
  reprocess: ReprocessState;
}

type IngestDataAction =
  | { type: "upload_queued"; entry: UploadEntry }
  | { type: "upload_started"; id: string }
  | { type: "upload_success"; id: string; response: UploadResponse }
  | { type: "upload_failed"; id: string; error: string }
  | { type: "url_added"; entry: UrlEntry }
  | { type: "url_started"; id: string }
  | { type: "url_success"; id: string; response: IngestUrlResponse }
  | { type: "url_failed"; id: string; error: string }
  | { type: "reprocess_open" }
  | { type: "reprocess_close" }
  | { type: "reprocess_started" }
  | { type: "reprocess_success"; response: ReprocessResponse }
  | { type: "reprocess_failed"; error: string };

const initialState: IngestDataState = {
  uploads: [],
  urls: [],
  reprocess: { status: "idle" },
};

function mapUpload(
  state: IngestDataState,
  id: string,
  update: (entry: UploadEntry) => UploadEntry,
): IngestDataState {
  return {
    ...state,
    uploads: state.uploads.map((u) => (u.id === id ? update(u) : u)),
  };
}

function mapUrl(
  state: IngestDataState,
  id: string,
  update: (entry: UrlEntry) => UrlEntry,
): IngestDataState {
  return {
    ...state,
    urls: state.urls.map((u) => (u.id === id ? update(u) : u)),
  };
}

export function ingestDataReducer(
  state: IngestDataState,
  action: IngestDataAction,
): IngestDataState {
  switch (action.type) {
    case "upload_queued":
      return { ...state, uploads: [...state.uploads, action.entry] };
    case "upload_started":
      return mapUpload(state, action.id, (u) => ({
        id: u.id,
        file: u.file,
        status: "uploading",
      }));
    case "upload_success":
      return mapUpload(state, action.id, (u) => ({
        id: u.id,
        file: u.file,
        status: "success",
        response: action.response,
      }));
    case "upload_failed":
      return mapUpload(state, action.id, (u) => ({
        id: u.id,
        file: u.file,
        status: "failed",
        error: action.error,
      }));
    case "url_added":
      return { ...state, urls: [...state.urls, action.entry] };
    case "url_started":
      return mapUrl(state, action.id, (u) => ({
        id: u.id,
        url: u.url,
        status: "submitting",
      }));
    case "url_success":
      return mapUrl(state, action.id, (u) => ({
        id: u.id,
        url: u.url,
        status: "success",
        response: action.response,
      }));
    case "url_failed":
      return mapUrl(state, action.id, (u) => ({
        ...u,
        status: "failed",
        error: action.error,
      }));
    case "reprocess_open":
      return { ...state, reprocess: { status: "confirming" } };
    case "reprocess_close":
      return { ...state, reprocess: { status: "idle" } };
    case "reprocess_started":
      return { ...state, reprocess: { status: "running" } };
    case "reprocess_success":
      return {
        ...state,
        reprocess: { status: "success", response: action.response },
      };
    case "reprocess_failed":
      return {
        ...state,
        reprocess: { status: "failed", error: action.error },
      };
  }
}

function newId(): string {
  return globalThis.crypto.randomUUID();
}

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot === -1) return "";
  return filename.slice(dot).toLowerCase();
}

function validateFile(file: File): string | null {
  const ext = fileExtension(file.name);
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(ext)) {
    return `Unsupported file extension "${ext || "(none)"}". Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}.`;
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return `File exceeds the 50 MiB limit (${sizeMb} MiB).`;
  }
  return null;
}

function validateUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed.length === 0) {
    return "URL is required.";
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "URL must use http:// or https://.";
    }
  } catch {
    return "URL is not well-formed.";
  }
  return null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function IngestData(): JSX.Element {
  const [state, dispatch] = useReducer(ingestDataReducer, initialState);
  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [confirmDraft, setConfirmDraft] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const runUpload = useCallback(
    async (id: string, file: File): Promise<void> => {
      dispatch({ type: "upload_started", id });
      try {
        const response = await uploadDocument(file);
        dispatch({ type: "upload_success", id, response });
      } catch (err) {
        dispatch({ type: "upload_failed", id, error: errorMessage(err) });
      }
    },
    [],
  );

  const queueFiles = useCallback(
    (files: FileList | File[]): void => {
      const list = Array.from(files);
      for (const file of list) {
        const id = newId();
        const validationError = validateFile(file);
        if (validationError !== null) {
          dispatch({
            type: "upload_queued",
            entry: {
              id,
              file,
              status: "failed",
              error: validationError,
            },
          });
          continue;
        }
        dispatch({
          type: "upload_queued",
          entry: { id, file, status: "pending" },
        });
        void runUpload(id, file);
      }
    },
    [runUpload],
  );

  const handleBrowseChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const { files } = event.target;
      if (files !== null && files.length > 0) {
        queueFiles(files);
      }
      event.target.value = "";
    },
    [queueFiles],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      const { files } = event.dataTransfer;
      if (files.length > 0) {
        queueFiles(files);
      }
    },
    [queueFiles],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
  }, []);

  const handleRetryUpload = useCallback(
    (entry: UploadEntry) => {
      // Validation was the failure -- do not re-fire the wire call.
      if (validateFile(entry.file) !== null) {
        return;
      }
      void runUpload(entry.id, entry.file);
    },
    [runUpload],
  );

  const handleAddUrl = useCallback(async (): Promise<void> => {
    const validationError = validateUrl(urlDraft);
    if (validationError !== null) {
      setUrlError(validationError);
      return;
    }
    setUrlError(null);
    const trimmed = urlDraft.trim();
    const id = newId();
    dispatch({
      type: "url_added",
      entry: { id, url: trimmed, status: "pending" },
    });
    setUrlDraft("");
    dispatch({ type: "url_started", id });
    try {
      const response = await addDocumentUrl(trimmed);
      dispatch({ type: "url_success", id, response });
    } catch (err) {
      dispatch({ type: "url_failed", id, error: errorMessage(err) });
    }
  }, [urlDraft]);

  const handleRetryUrl = useCallback(async (entry: UrlEntry): Promise<void> => {
    dispatch({ type: "url_started", id: entry.id });
    try {
      const response = await addDocumentUrl(entry.url);
      dispatch({ type: "url_success", id: entry.id, response });
    } catch (err) {
      dispatch({ type: "url_failed", id: entry.id, error: errorMessage(err) });
    }
  }, []);

  const handleReprocessOpen = useCallback(() => {
    setConfirmDraft("");
    dispatch({ type: "reprocess_open" });
  }, []);

  const handleReprocessCancel = useCallback(() => {
    setConfirmDraft("");
    dispatch({ type: "reprocess_close" });
  }, []);

  const handleReprocessConfirm = useCallback(async (): Promise<void> => {
    if (confirmDraft !== REPROCESS_CONFIRM_TOKEN) {
      return;
    }
    dispatch({ type: "reprocess_started" });
    try {
      const response = await reprocessAll();
      dispatch({ type: "reprocess_success", response });
    } catch (err) {
      dispatch({ type: "reprocess_failed", error: errorMessage(err) });
    } finally {
      setConfirmDraft("");
    }
  }, [confirmDraft]);

  const confirmEnabled = confirmDraft === REPROCESS_CONFIRM_TOKEN;
  const reprocessBusy = state.reprocess.status === "running";

  return (
    <section
      aria-label="ingest data"
      data-testid="ingest-data"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Ingest data</h2>
        <p className={styles.pageHint}>
          Upload files, queue URLs, or reprocess the existing corpus.
          All actions run as the signed-in admin.
        </p>
      </header>

      <section
        aria-label="upload files"
        data-testid="upload-section"
        className={styles.section}
      >
        <h3 className={styles.sectionTitle}>Upload files</h3>
        <p className={styles.sectionHint}>
          {`Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}. Max 50 MiB per file.`}
        </p>
        <div
          data-testid="upload-dropzone"
          className={styles.dropzone}
          data-dragging={isDragging ? "true" : "false"}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <p className={styles.dropzoneText}>
            Drag and drop files here, or
          </p>
          <Button
            appearance="primary"
            onClick={() => {
              fileInputRef.current?.click();
            }}
          >
            Browse files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={handleBrowseChange}
            data-testid="upload-input"
            className={styles.hiddenInput}
            aria-label="Browse files"
          />
        </div>
        {state.uploads.length > 0 ? (
          <ul
            data-testid="upload-list"
            className={styles.entryList}
          >
            {state.uploads.map((entry) => (
              <li
                key={entry.id}
                data-testid={`upload-entry-${entry.id}`}
                data-status={entry.status}
                className={styles.entry}
              >
                <span className={styles.entryName}>{entry.file.name}</span>
                <span className={styles.entryMeta}>
                  {formatSize(entry.file.size)}
                </span>
                <span
                  className={styles.entryStatus}
                  data-testid={`upload-status-${entry.id}`}
                >
                  {entry.status}
                </span>
                {entry.status === "failed" && entry.error !== undefined ? (
                  <span
                    className={styles.entryError}
                    data-testid={`upload-error-${entry.id}`}
                  >
                    {entry.error}
                  </span>
                ) : null}
                {entry.status === "failed" ? (
                  <Button
                    appearance="secondary"
                    size="small"
                    onClick={() => {
                      handleRetryUpload(entry);
                    }}
                    data-testid={`upload-retry-${entry.id}`}
                  >
                    Retry
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section
        aria-label="add url"
        data-testid="url-section"
        className={styles.section}
      >
        <h3 className={styles.sectionTitle}>Add URL</h3>
        <p className={styles.sectionHint}>
          Fetch, parse, embed, and index a single web page.
        </p>
        <form
          className={styles.urlForm}
          onSubmit={(event) => {
            event.preventDefault();
            void handleAddUrl();
          }}
        >
          <label htmlFor="ingest-url-input" className={styles.urlLabel}>
            URL
          </label>
          <Input
            id="ingest-url-input"
            value={urlDraft}
            onChange={(_event, data) => {
              setUrlDraft(data.value);
              if (urlError !== null) {
                setUrlError(null);
              }
            }}
            placeholder="https://docs.example.com/article"
            className={styles.urlInput}
            data-testid="url-input"
          />
          <Button
            appearance="primary"
            type="submit"
            data-testid="url-submit"
          >
            Add
          </Button>
        </form>
        {urlError !== null ? (
          <p className={styles.urlError} data-testid="url-validation-error">
            {urlError}
          </p>
        ) : null}
        {state.urls.length > 0 ? (
          <ul data-testid="url-list" className={styles.entryList}>
            {state.urls.map((entry) => (
              <li
                key={entry.id}
                data-testid={`url-entry-${entry.id}`}
                data-status={entry.status}
                className={styles.entry}
              >
                <span className={styles.entryName}>{entry.url}</span>
                <span
                  className={styles.entryStatus}
                  data-testid={`url-status-${entry.id}`}
                >
                  {entry.status}
                </span>
                {entry.status === "success" &&
                entry.response !== undefined ? (
                  <span
                    className={styles.entryMeta}
                    data-testid={`url-doc-count-${entry.id}`}
                  >
                    {`${entry.response.document_count.toString()} chunks`}
                  </span>
                ) : null}
                {entry.status === "failed" && entry.error !== undefined ? (
                  <span
                    className={styles.entryError}
                    data-testid={`url-error-${entry.id}`}
                  >
                    {entry.error}
                  </span>
                ) : null}
                {entry.status === "failed" ? (
                  <Button
                    appearance="secondary"
                    size="small"
                    onClick={() => {
                      void handleRetryUrl(entry);
                    }}
                    data-testid={`url-retry-${entry.id}`}
                  >
                    Retry
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section
        aria-label="reprocess all"
        data-testid="reprocess-section"
        className={styles.section}
      >
        <h3 className={styles.sectionTitle}>Reprocess all documents</h3>
        <p className={styles.sectionHint}>
          Re-parse, re-embed, and re-push every blob in the documents
          container through the indexing pipeline.
        </p>
        <Button
          appearance="primary"
          onClick={handleReprocessOpen}
          disabled={reprocessBusy}
          data-testid="reprocess-open"
        >
          Reprocess all
        </Button>
        {state.reprocess.status === "success" &&
        state.reprocess.response !== undefined ? (
          <p
            className={styles.reprocessSuccess}
            data-testid="reprocess-success"
          >
            {`Enqueued ${state.reprocess.response.enqueued_count.toString()} document(s) for reprocessing.`}
          </p>
        ) : null}
        {state.reprocess.status === "failed" &&
        state.reprocess.error !== undefined ? (
          <p
            className={styles.reprocessError}
            data-testid="reprocess-error"
          >
            {state.reprocess.error}
          </p>
        ) : null}
      </section>

      {state.reprocess.status === "confirming" ||
      state.reprocess.status === "running" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm reprocess"
          data-testid="reprocess-confirm-dialog"
          className={styles.dialogBackdrop}
        >
          <div className={styles.dialog}>
            <h3 className={styles.dialogTitle}>Confirm reprocess</h3>
            <p>
              {`This re-fans every blob in the documents container. Type ${REPROCESS_CONFIRM_TOKEN} to confirm.`}
            </p>
            <Input
              aria-label="Type REPROCESS to confirm"
              value={confirmDraft}
              onChange={(_event, data) => {
                setConfirmDraft(data.value);
              }}
              disabled={reprocessBusy}
              data-testid="reprocess-confirm-input"
            />
            <div className={styles.dialogActions}>
              <Button
                appearance="secondary"
                onClick={handleReprocessCancel}
                disabled={reprocessBusy}
                data-testid="reprocess-cancel"
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={!confirmEnabled || reprocessBusy}
                onClick={() => {
                  void handleReprocessConfirm();
                }}
                data-testid="reprocess-confirm"
              >
                {reprocessBusy ? "Reprocessing…" : "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
