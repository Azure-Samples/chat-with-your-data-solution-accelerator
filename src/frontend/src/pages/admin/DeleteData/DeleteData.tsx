/**
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
import { deleteDocument, listDocuments } from "@/api/admin";
import type { SourceListing } from "@/models/admin";
import {
  LoadStatus,
  RowDeleteStatus,
} from "@/models/status";
import styles from "./DeleteData.module.css";

interface RowState {
  listing: SourceListing;
  deleteStatus: RowDeleteStatus;
  deleteError?: string;
}

interface DeleteDataState {
  listStatus: LoadStatus;
  listError: string | null;
  rows: RowState[];
  selectedSources: string[];
  pendingDeleteSources: string[] | null;
}

export const DeleteActionType = {
  ListStarted: "list_started",
  ListSucceeded: "list_succeeded",
  ListFailed: "list_failed",
  ToggleSelected: "toggle_selected",
  SelectAll: "select_all",
  ConfirmOpen: "confirm_open",
  ConfirmClose: "confirm_close",
  DeleteStarted: "delete_started",
  DeleteSucceeded: "delete_succeeded",
  DeleteFailed: "delete_failed",
} as const;
export type DeleteActionType =
  (typeof DeleteActionType)[keyof typeof DeleteActionType];

type DeleteDataAction =
  | { type: typeof DeleteActionType.ListStarted }
  | { type: typeof DeleteActionType.ListSucceeded; listings: SourceListing[] }
  | { type: typeof DeleteActionType.ListFailed; error: string }
  | { type: typeof DeleteActionType.ToggleSelected; source: string }
  | { type: typeof DeleteActionType.SelectAll; selected: boolean }
  | { type: typeof DeleteActionType.ConfirmOpen; sources: string[] }
  | { type: typeof DeleteActionType.ConfirmClose }
  | { type: typeof DeleteActionType.DeleteStarted; source: string }
  | { type: typeof DeleteActionType.DeleteSucceeded; source: string }
  | { type: typeof DeleteActionType.DeleteFailed; source: string; error: string };

const initialState: DeleteDataState = {
  listStatus: LoadStatus.Loading,
  listError: null,
  rows: [],
  selectedSources: [],
  pendingDeleteSources: null,
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
    case DeleteActionType.ListStarted:
      return {
        listStatus: LoadStatus.Loading,
        listError: null,
        rows: [],
        selectedSources: [],
        pendingDeleteSources: null,
      };
    case DeleteActionType.ListSucceeded:
      return {
        listStatus: LoadStatus.Loaded,
        listError: null,
        rows: action.listings.map((listing) => ({
          listing,
          deleteStatus: RowDeleteStatus.Idle,
        })),
        selectedSources: [],
        pendingDeleteSources: null,
      };
    case DeleteActionType.ListFailed:
      return {
        listStatus: LoadStatus.Failed,
        listError: action.error,
        rows: [],
        selectedSources: [],
        pendingDeleteSources: null,
      };
    case DeleteActionType.ToggleSelected:
      if (!state.rows.some((row) => row.listing.source === action.source)) {
        return state;
      }
      return {
        ...state,
        selectedSources: state.selectedSources.includes(action.source)
          ? state.selectedSources.filter((source) => source !== action.source)
          : [...state.selectedSources, action.source],
      };
    case DeleteActionType.SelectAll:
      return {
        ...state,
        selectedSources: action.selected
          ? state.rows.map((row) => row.listing.source)
          : [],
      };
    case DeleteActionType.ConfirmOpen:
      return {
        ...state,
        pendingDeleteSources:
          action.sources.length > 0 ? action.sources : null,
      };
    case DeleteActionType.ConfirmClose:
      return { ...state, pendingDeleteSources: null };
    case DeleteActionType.DeleteStarted:
      return mapRow(
        { ...state, pendingDeleteSources: null },
        action.source,
        (row) => ({
          listing: row.listing,
          deleteStatus: RowDeleteStatus.Deleting,
        }),
      );
    case DeleteActionType.DeleteSucceeded:
      return {
        ...state,
        selectedSources: state.selectedSources.filter(
          (source) => source !== action.source,
        ),
        rows: state.rows.filter(
          (row) => row.listing.source !== action.source,
        ),
      };
    case DeleteActionType.DeleteFailed:
      return mapRow(state, action.source, (row) => ({
        listing: row.listing,
        deleteStatus: RowDeleteStatus.Failed,
        deleteError: action.error,
      }));
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function formatLastModified(value: string | null): string {
  if (value === null) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const yy = String(date.getUTCFullYear() % 100).padStart(2, "0");
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const min = String(date.getUTCMinutes()).padStart(2, "0");
  return `${mm}/${dd}/${yy} ${hh}:${min}`;
}

export function DeleteData(): JSX.Element {
  const [state, dispatch] = useReducer(deleteDataReducer, initialState);
  const selectedSet = new Set(state.selectedSources);
  const selectedFailedSources = state.rows
    .filter(
      (row) =>
        selectedSet.has(row.listing.source) &&
        row.deleteStatus === RowDeleteStatus.Failed,
    )
    .map((row) => row.listing.source);
  const isAllSelected =
    state.rows.length > 0 &&
    state.rows.every((row) => selectedSet.has(row.listing.source));
  const hasAnyLastModified = state.rows.some(
    (row) => row.listing.last_modified !== null,
  );

  const refresh = useCallback(async (): Promise<void> => {
    dispatch({ type: DeleteActionType.ListStarted });
    try {
      const response = await listDocuments();
      dispatch({
        type: DeleteActionType.ListSucceeded,
        listings: response.documents,
      });
    } catch (err) {
      dispatch({ type: DeleteActionType.ListFailed, error: errorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleConfirmOpen = useCallback((sources: string[]) => {
    dispatch({ type: DeleteActionType.ConfirmOpen, sources });
  }, []);

  const handleConfirmCancel = useCallback(() => {
    dispatch({ type: DeleteActionType.ConfirmClose });
  }, []);

  const handleConfirmDelete = useCallback(async (): Promise<void> => {
    const sources = state.pendingDeleteSources;
    if (sources === null || sources.length === 0) {
      return;
    }
    let allSucceeded = true;
    for (const source of sources) {
      dispatch({ type: DeleteActionType.DeleteStarted, source });
      try {
        await deleteDocument(source);
        dispatch({ type: DeleteActionType.DeleteSucceeded, source });
      } catch (err) {
        allSucceeded = false;
        dispatch({
          type: DeleteActionType.DeleteFailed,
          source,
          error: errorMessage(err),
        });
      }
    }
    // A fully-successful batch re-syncs the listing with the server so the
    // table reflects server truth rather than only the optimistic per-row
    // removals. A partial failure skips the refresh so the failed rows keep
    // their inline error and retry affordance.
    if (allSucceeded) {
      await refresh();
    }
  }, [state.pendingDeleteSources, refresh]);

  const handleRetryDelete = useCallback((source: string) => {
    dispatch({ type: DeleteActionType.ConfirmOpen, sources: [source] });
  }, []);

  const handleToggleSelected = useCallback((source: string) => {
    dispatch({ type: DeleteActionType.ToggleSelected, source });
  }, []);

  const handleSelectAll = useCallback((selected: boolean) => {
    dispatch({ type: DeleteActionType.SelectAll, selected });
  }, []);

  return (
    <section
      aria-label="data set"
      data-testid="delete-data"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Data set</h2>
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
          <div className={styles.sectionActions}>
            <Button
              appearance="secondary"
              onClick={() => {
                handleConfirmOpen(selectedFailedSources);
              }}
              disabled={selectedFailedSources.length === 0}
              data-testid="bulk-retry-failed-button"
            >
              Retry selected failed ({selectedFailedSources.length.toString()})
            </Button>
            <Button
              appearance="secondary"
              onClick={() => {
                handleConfirmOpen(state.selectedSources);
              }}
              disabled={state.selectedSources.length === 0}
              data-testid="bulk-delete-button"
            >
              Delete selected ({state.selectedSources.length.toString()})
            </Button>
            <Button
              appearance="secondary"
              onClick={() => {
                void refresh();
              }}
              disabled={state.listStatus === LoadStatus.Loading}
              data-testid="refresh-button"
            >
              Refresh
            </Button>
          </div>
        </div>

        {state.listStatus === LoadStatus.Loading ? (
          <p className={styles.statusMessage} data-testid="loading-message">
            Loading sources…
          </p>
        ) : null}

        {state.listStatus === LoadStatus.Failed ? (
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

        {state.listStatus === LoadStatus.Loaded && state.rows.length === 0 ? (
          <p className={styles.statusMessage} data-testid="empty-message">
            No sources are currently indexed.
          </p>
        ) : null}

        {state.listStatus === LoadStatus.Loaded && state.rows.length > 0 ? (
          <table
            className={styles.table}
            data-testid="source-table"
            aria-label="indexed sources"
          >
            <thead>
              <tr>
                <th scope="col" className={styles.selectColumn}>
                  <label className={styles.selectAllControl}>
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={(event) => {
                        handleSelectAll(event.currentTarget.checked);
                      }}
                      data-testid="select-all"
                    />
                    <span>Select</span>
                  </label>
                </th>
                <th scope="col">Source</th>
                <th scope="col">Chunks</th>
                {hasAnyLastModified ? (
                  <th scope="col">Last modified</th>
                ) : null}
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
                  <td className={styles.selectColumn}>
                    <input
                      type="checkbox"
                      checked={selectedSet.has(row.listing.source)}
                      onChange={() => {
                        handleToggleSelected(row.listing.source);
                      }}
                      disabled={
                        row.deleteStatus === RowDeleteStatus.Deleting
                      }
                      data-testid={`row-select-${row.listing.source}`}
                      aria-label={`Select ${row.listing.source}`}
                    />
                  </td>
                  <td className={styles.rowSource}>
                    {row.listing.source}
                    {row.deleteStatus === RowDeleteStatus.Failed &&
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
                  {hasAnyLastModified ? (
                    <td className={styles.rowMeta}>
                      {formatLastModified(row.listing.last_modified)}
                    </td>
                  ) : null}
                  <td className={styles.rowActions}>
                    {row.deleteStatus === RowDeleteStatus.Failed ? (
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
                        disabled={
                          row.deleteStatus === RowDeleteStatus.Deleting
                        }
                        onClick={() => {
                          handleConfirmOpen([row.listing.source]);
                        }}
                        data-testid={`row-delete-${row.listing.source}`}
                      >
                        {row.deleteStatus === RowDeleteStatus.Deleting
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

      {state.pendingDeleteSources !== null
        ? (() => {
            const sources = state.pendingDeleteSources;
            const [firstSource] = sources;
            const target =
              sources.length === 1 && firstSource !== undefined
                ? firstSource
                : `${sources.length.toString()} selected sources`;
            return (
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
                    This permanently removes every indexed chunk attached to:
                  </p>
                  <p className={styles.dialogTarget}>{target}</p>
                  <p className={styles.dialogBody}>
                    The action cannot be undone.
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
            );
          })()
        : null}
    </section>
  );
}
