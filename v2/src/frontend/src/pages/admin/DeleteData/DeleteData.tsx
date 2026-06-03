/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Admin "Delete Data" page. Lists every distinct source currently
 * indexed and lets the operator remove every chunk attached to a
 * chosen source via the backend `DELETE /api/admin/documents/{source}`
 * route.
 *
 * One section, four states (all first-class renders, no thrown
 * exceptions ever reach the user):
 *
 * 1. **Loading** -- on mount and on Refresh, `listDocuments()` is
 *    fired and the table is replaced with a status message.
 * 2. **Failed** -- the wire call rejected; the error message is
 *    surfaced and a Retry button re-fires the list call.
 * 3. **Empty** -- the call succeeded but the index has no sources;
 *    the operator sees an explicit empty-state message instead of a
 *    blank table.
 * 4. **Loaded** -- one row per source with the chunk count, last
 *    modified timestamp (when available), and a per-row Delete
 *    button that opens a confirmation dialog.
 *
 * All wire interactions route through `src/api/admin.tsx`, never
 * `fetch` directly -- the page is wire-shape-agnostic.
 */
import {
  useCallback,
  useEffect,
  useReducer,
  type JSX,
} from "react";
import { Button } from "@fluentui/react-components";
import { deleteDocument, listDocuments } from "../../../api/admin";
import type { SourceListing } from "../../../models/admin";
import styles from "./DeleteData.module.css";

type ListStatus = "loading" | "loaded" | "failed";
type RowDeleteStatus = "idle" | "deleting" | "failed";

interface RowState {
  listing: SourceListing;
  deleteStatus: RowDeleteStatus;
  deleteError?: string;
}

interface DeleteDataState {
  listStatus: ListStatus;
  listError: string | null;
  rows: RowState[];
  pendingDeleteSource: string | null;
}

type DeleteDataAction =
  | { type: "list_started" }
  | { type: "list_succeeded"; listings: SourceListing[] }
  | { type: "list_failed"; error: string }
  | { type: "confirm_open"; source: string }
  | { type: "confirm_close" }
  | { type: "delete_started"; source: string }
  | { type: "delete_succeeded"; source: string }
  | { type: "delete_failed"; source: string; error: string };

const initialState: DeleteDataState = {
  listStatus: "loading",
  listError: null,
  rows: [],
  pendingDeleteSource: null,
};

function mapRow(
  state: DeleteDataState,
  source: string,
  update: (row: RowState) => RowState,
): DeleteDataState {
  return {
    ...state,
    rows: state.rows.map((row) =>
      row.listing.source === source ? update(row) : row,
    ),
  };
}

export function deleteDataReducer(
  state: DeleteDataState,
  action: DeleteDataAction,
): DeleteDataState {
  switch (action.type) {
    case "list_started":
      return {
        listStatus: "loading",
        listError: null,
        rows: [],
        pendingDeleteSource: null,
      };
    case "list_succeeded":
      return {
        listStatus: "loaded",
        listError: null,
        rows: action.listings.map((listing) => ({
          listing,
          deleteStatus: "idle",
        })),
        pendingDeleteSource: null,
      };
    case "list_failed":
      return {
        listStatus: "failed",
        listError: action.error,
        rows: [],
        pendingDeleteSource: null,
      };
    case "confirm_open":
      return { ...state, pendingDeleteSource: action.source };
    case "confirm_close":
      return { ...state, pendingDeleteSource: null };
    case "delete_started":
      return mapRow(
        { ...state, pendingDeleteSource: null },
        action.source,
        (row) => ({
          listing: row.listing,
          deleteStatus: "deleting",
        }),
      );
    case "delete_succeeded":
      return {
        ...state,
        rows: state.rows.filter(
          (row) => row.listing.source !== action.source,
        ),
      };
    case "delete_failed":
      return mapRow(state, action.source, (row) => ({
        listing: row.listing,
        deleteStatus: "failed",
        deleteError: action.error,
      }));
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function formatLastModified(value: string | null): string {
  return value ?? "—";
}

export function DeleteData(): JSX.Element {
  const [state, dispatch] = useReducer(deleteDataReducer, initialState);

  const refresh = useCallback(async (): Promise<void> => {
    dispatch({ type: "list_started" });
    try {
      const response = await listDocuments();
      dispatch({ type: "list_succeeded", listings: response.documents });
    } catch (err) {
      dispatch({ type: "list_failed", error: errorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleConfirmOpen = useCallback((source: string) => {
    dispatch({ type: "confirm_open", source });
  }, []);

  const handleConfirmCancel = useCallback(() => {
    dispatch({ type: "confirm_close" });
  }, []);

  const handleConfirmDelete = useCallback(async (): Promise<void> => {
    const source = state.pendingDeleteSource;
    if (source === null) {
      return;
    }
    dispatch({ type: "delete_started", source });
    try {
      await deleteDocument(source);
      dispatch({ type: "delete_succeeded", source });
    } catch (err) {
      dispatch({ type: "delete_failed", source, error: errorMessage(err) });
    }
  }, [state.pendingDeleteSource]);

  const handleRetryDelete = useCallback((source: string) => {
    dispatch({ type: "confirm_open", source });
  }, []);

  return (
    <section
      aria-label="delete data"
      data-testid="delete-data"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Delete data</h2>
        <p className={styles.pageHint}>
          Review every distinct source currently indexed and remove
          ones that should no longer be queryable.
        </p>
      </header>

      <section
        aria-label="source listing"
        data-testid="source-listing-section"
        className={styles.section}
      >
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Indexed sources</h3>
          <Button
            appearance="secondary"
            onClick={() => {
              void refresh();
            }}
            disabled={state.listStatus === "loading"}
            data-testid="refresh-button"
          >
            Refresh
          </Button>
        </div>

        {state.listStatus === "loading" ? (
          <p className={styles.statusMessage} data-testid="loading-message">
            Loading sources…
          </p>
        ) : null}

        {state.listStatus === "failed" ? (
          <>
            <p className={styles.errorMessage} data-testid="list-error">
              {state.listError ?? "Failed to load sources."}
            </p>
            <div>
              <Button
                appearance="primary"
                onClick={() => {
                  void refresh();
                }}
                data-testid="list-retry"
              >
                Retry
              </Button>
            </div>
          </>
        ) : null}

        {state.listStatus === "loaded" && state.rows.length === 0 ? (
          <p className={styles.statusMessage} data-testid="empty-message">
            No sources are currently indexed.
          </p>
        ) : null}

        {state.listStatus === "loaded" && state.rows.length > 0 ? (
          <table
            className={styles.table}
            data-testid="source-table"
            aria-label="indexed sources"
          >
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Chunks</th>
                <th scope="col">Last modified</th>
                <th scope="col" className={styles.rowActions}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((row) => (
                <tr
                  key={row.listing.source}
                  data-testid={`source-row-${row.listing.source}`}
                  data-status={row.deleteStatus}
                >
                  <td className={styles.rowSource}>
                    {row.listing.source}
                    {row.deleteStatus === "failed" &&
                    row.deleteError !== undefined ? (
                      <div
                        className={styles.rowError}
                        data-testid={`row-error-${row.listing.source}`}
                      >
                        {row.deleteError}
                      </div>
                    ) : null}
                  </td>
                  <td className={styles.rowMeta}>
                    {row.listing.chunk_count.toString()}
                  </td>
                  <td className={styles.rowMeta}>
                    {formatLastModified(row.listing.last_modified)}
                  </td>
                  <td className={styles.rowActions}>
                    {row.deleteStatus === "failed" ? (
                      <Button
                        appearance="secondary"
                        size="small"
                        onClick={() => {
                          handleRetryDelete(row.listing.source);
                        }}
                        data-testid={`row-retry-${row.listing.source}`}
                      >
                        Retry
                      </Button>
                    ) : (
                      <Button
                        appearance="secondary"
                        size="small"
                        disabled={row.deleteStatus === "deleting"}
                        onClick={() => {
                          handleConfirmOpen(row.listing.source);
                        }}
                        data-testid={`row-delete-${row.listing.source}`}
                      >
                        {row.deleteStatus === "deleting"
                          ? "Deleting…"
                          : "Delete"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      {state.pendingDeleteSource !== null ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete"
          data-testid="delete-confirm-dialog"
          className={styles.dialogBackdrop}
        >
          <div className={styles.dialog}>
            <h3 className={styles.dialogTitle}>Confirm delete</h3>
            <p className={styles.dialogBody}>
              This permanently removes every indexed chunk attached to{" "}
              <span className={styles.dialogTarget}>
                {state.pendingDeleteSource}
              </span>
              . The action cannot be undone.
            </p>
            <div className={styles.dialogActions}>
              <Button
                appearance="secondary"
                onClick={handleConfirmCancel}
                data-testid="delete-cancel"
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                onClick={() => {
                  void handleConfirmDelete();
                }}
                data-testid="delete-confirm"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
