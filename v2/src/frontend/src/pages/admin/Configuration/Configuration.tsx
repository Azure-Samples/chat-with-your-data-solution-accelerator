/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Admin "Configuration" page. Surfaces the seven-field
 * runtime-toggle subset of `AppSettings` and lets the operator
 * patch any subset of those fields via RFC 7396 JSON Merge Patch.
 *
 * One section, four first-class states (no thrown exception ever
 * reaches the user):
 *
 * 1. **Loading** -- on mount and on Retry, `getAdminConfig()` is
 *    fired and the form is replaced with a status message.
 * 2. **Failed** -- the wire call rejected; the error message is
 *    surfaced and a Retry button re-fires the GET.
 * 3. **Loaded (clean)** -- the seven inputs render the effective
 *    server values; Save / Discard are disabled until the operator
 *    edits a field.
 * 4. **Loaded (dirty)** -- Save and Discard become active. Save
 *    PATCHes only the changed fields (RFC 7396 absent-key
 *    semantics: untouched fields stay untouched server-side).
 *
 * Per-field client-side validation (number bounds, non-empty
 * strings) keeps invalid edits out of the wire; the typed client
 * already enforces a server-side 422 ladder for anything that
 * slips past.
 *
 * All wire interactions route through `src/api/admin.tsx`, never
 * `fetch` directly -- the page is wire-shape-agnostic.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  type ChangeEvent,
  type JSX,
} from "react";
import { Button, Input, Switch } from "@fluentui/react-components";
import type { SwitchOnChangeData } from "@fluentui/react-components";
import { getAdminConfig, patchAdminConfig } from "@/api/admin";
import type {
  AdminConfig,
  AdminConfigPatch,
  RuntimeConfig,
} from "@/models/admin";
import {
  LoadStatus,
  SaveStatus,
} from "@/models/status";
import styles from "./Configuration.module.css";

/**
 * One row in the seven-field form. `key` is the wire-shape field
 * name (must match `AdminConfig` + the backend `WRITABLE_FIELDS`
 * allow-list verbatim).
 */
interface FieldSpec {
  key: keyof AdminConfig;
  label: string;
  hint: string;
  kind: "text" | "number" | "boolean";
  numberStep?: string;
  numberMin?: number;
  numberMax?: number;
}

const FIELD_SPECS: readonly FieldSpec[] = [
  {
    key: "orchestrator_name",
    label: "Orchestrator",
    hint: "Registry key of the active orchestrator (e.g. langgraph, agent_framework).",
    kind: "text",
  },
  {
    key: "openai_temperature",
    label: "OpenAI temperature",
    hint: "Sampling temperature for the chat model. 0.0 = deterministic, 2.0 = maximally random.",
    kind: "number",
    numberStep: "0.05",
    numberMin: 0,
    numberMax: 2,
  },
  {
    key: "openai_max_tokens",
    label: "OpenAI max tokens",
    hint: "Maximum number of tokens the chat model may generate per response.",
    kind: "number",
    numberStep: "1",
    numberMin: 1,
  },
  {
    key: "search_use_semantic_search",
    label: "Use semantic search",
    hint: "Enable Azure AI Search semantic reranking on retrieval queries.",
    kind: "boolean",
  },
  {
    key: "search_top_k",
    label: "Search top K",
    hint: "Number of chunks to retrieve per query before reranking.",
    kind: "number",
    numberStep: "1",
    numberMin: 1,
  },
  {
    key: "log_level",
    label: "Log level",
    hint: "Python logging level for the backend process (DEBUG, INFO, WARNING, ERROR).",
    kind: "text",
  },
  {
    key: "content_safety_enabled",
    label: "Content safety",
    hint: "Enable the Azure AI Content Safety pre-filter on user input.",
    kind: "boolean",
  },
] as const;

type FieldValue = string | number | boolean;
type FormValues = Record<keyof AdminConfig, FieldValue>;

interface ConfigurationState {
  loadStatus: LoadStatus;
  loadError: string | null;
  serverConfig: AdminConfig | null;
  formValues: FormValues | null;
  saveStatus: SaveStatus;
  saveError: string | null;
  lastRuntime: RuntimeConfig | null;
}

export const ConfigActionType = {
  LoadStarted: "load_started",
  LoadSucceeded: "load_succeeded",
  LoadFailed: "load_failed",
  FieldChanged: "field_changed",
  Discard: "discard",
  SaveStarted: "save_started",
  SaveSucceeded: "save_succeeded",
  SaveFailed: "save_failed",
} as const;
export type ConfigActionType =
  (typeof ConfigActionType)[keyof typeof ConfigActionType];

type ConfigurationAction =
  | { type: typeof ConfigActionType.LoadStarted }
  | { type: typeof ConfigActionType.LoadSucceeded; config: AdminConfig }
  | { type: typeof ConfigActionType.LoadFailed; error: string }
  | {
      type: typeof ConfigActionType.FieldChanged;
      key: keyof AdminConfig;
      value: FieldValue;
    }
  | { type: typeof ConfigActionType.Discard }
  | { type: typeof ConfigActionType.SaveStarted }
  | {
      type: typeof ConfigActionType.SaveSucceeded;
      runtime: RuntimeConfig;
      refreshed: AdminConfig;
    }
  | { type: typeof ConfigActionType.SaveFailed; error: string };

const initialState: ConfigurationState = {
  loadStatus: LoadStatus.Loading,
  loadError: null,
  serverConfig: null,
  formValues: null,
  saveStatus: SaveStatus.Idle,
  saveError: null,
  lastRuntime: null,
};

function configToForm(config: AdminConfig): FormValues {
  return {
    orchestrator_name: config.orchestrator_name,
    openai_temperature: config.openai_temperature,
    openai_max_tokens: config.openai_max_tokens,
    search_use_semantic_search: config.search_use_semantic_search,
    search_top_k: config.search_top_k,
    log_level: config.log_level,
    content_safety_enabled: config.content_safety_enabled,
  };
}

export function configurationReducer(
  state: ConfigurationState,
  action: ConfigurationAction,
): ConfigurationState {
  switch (action.type) {
    case ConfigActionType.LoadStarted:
      return {
        ...state,
        loadStatus: LoadStatus.Loading,
        loadError: null,
        saveStatus: SaveStatus.Idle,
        saveError: null,
      };
    case ConfigActionType.LoadSucceeded:
      return {
        loadStatus: LoadStatus.Loaded,
        loadError: null,
        serverConfig: action.config,
        formValues: configToForm(action.config),
        saveStatus: SaveStatus.Idle,
        saveError: null,
        lastRuntime: state.lastRuntime,
      };
    case ConfigActionType.LoadFailed:
      return {
        ...state,
        loadStatus: LoadStatus.Failed,
        loadError: action.error,
        serverConfig: null,
        formValues: null,
      };
    case ConfigActionType.FieldChanged:
      if (state.formValues === null) {
        return state;
      }
      return {
        ...state,
        formValues: { ...state.formValues, [action.key]: action.value },
        saveStatus:
          state.saveStatus === SaveStatus.Success
            ? SaveStatus.Idle
            : state.saveStatus,
      };
    case ConfigActionType.Discard:
      if (state.serverConfig === null) {
        return state;
      }
      return {
        ...state,
        formValues: configToForm(state.serverConfig),
        saveStatus: SaveStatus.Idle,
        saveError: null,
      };
    case ConfigActionType.SaveStarted:
      return {
        ...state,
        saveStatus: SaveStatus.Saving,
        saveError: null,
      };
    case ConfigActionType.SaveSucceeded:
      return {
        loadStatus: LoadStatus.Loaded,
        loadError: null,
        serverConfig: action.refreshed,
        formValues: configToForm(action.refreshed),
        saveStatus: SaveStatus.Success,
        saveError: null,
        lastRuntime: action.runtime,
      };
    case ConfigActionType.SaveFailed:
      return {
        ...state,
        saveStatus: SaveStatus.Failed,
        saveError: action.error,
      };
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Compute the RFC 7396 patch payload from the current form values.
 * Only fields that differ from the server-known config are included,
 * so an untouched form sends `{}` (a no-op touch) and an edited form
 * sends just the deltas. Number fields are sent as numbers; boolean
 * fields as booleans; string fields as strings -- matching the
 * `AdminConfigPatch` wire shape verbatim.
 */
function computePatch(
  serverConfig: AdminConfig,
  formValues: FormValues,
): AdminConfigPatch {
  const patch: AdminConfigPatch = {};
  for (const spec of FIELD_SPECS) {
    const before: FieldValue = serverConfig[spec.key];
    const after: FieldValue = formValues[spec.key];
    if (before === after) {
      continue;
    }
    switch (spec.key) {
      case "orchestrator_name":
        patch.orchestrator_name = after as string;
        break;
      case "openai_temperature":
        patch.openai_temperature = after as number;
        break;
      case "openai_max_tokens":
        patch.openai_max_tokens = after as number;
        break;
      case "search_use_semantic_search":
        patch.search_use_semantic_search = after as boolean;
        break;
      case "search_top_k":
        patch.search_top_k = after as number;
        break;
      case "log_level":
        patch.log_level = after as string;
        break;
      case "content_safety_enabled":
        patch.content_safety_enabled = after as boolean;
        break;
    }
  }
  return patch;
}

function isDirty(
  serverConfig: AdminConfig | null,
  formValues: FormValues | null,
): boolean {
  if (serverConfig === null || formValues === null) {
    return false;
  }
  for (const spec of FIELD_SPECS) {
    if (serverConfig[spec.key] !== formValues[spec.key]) {
      return true;
    }
  }
  return false;
}

/**
 * Validate a single field's current value. Returns `null` when the
 * value is acceptable, or a user-facing error message otherwise.
 * Number bounds match the form spec; strings must be non-empty after
 * trimming. The backend re-validates everything with Pydantic, so
 * the client-side check is purely a UX guard.
 */
function validateField(spec: FieldSpec, value: FieldValue): string | null {
  if (spec.kind === "text") {
    if (typeof value !== "string" || value.trim().length === 0) {
      return `${spec.label} cannot be empty.`;
    }
    return null;
  }
  if (spec.kind === "number") {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return `${spec.label} must be a number.`;
    }
    if (spec.numberMin !== undefined && value < spec.numberMin) {
      return `${spec.label} must be ${spec.numberMin.toString()} or greater.`;
    }
    if (spec.numberMax !== undefined && value > spec.numberMax) {
      return `${spec.label} must be ${spec.numberMax.toString()} or less.`;
    }
    return null;
  }
  return null;
}

function formatTimestamp(value: string): string {
  if (value === "") {
    return "—";
  }
  return value;
}

function formatActor(value: string): string {
  if (value === "") {
    return "—";
  }
  return value;
}

export function Configuration(): JSX.Element {
  const [state, dispatch] = useReducer(configurationReducer, initialState);

  const load = useCallback(async (): Promise<void> => {
    dispatch({ type: ConfigActionType.LoadStarted });
    try {
      const config = await getAdminConfig();
      dispatch({ type: ConfigActionType.LoadSucceeded, config });
    } catch (err) {
      dispatch({ type: ConfigActionType.LoadFailed, error: errorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const fieldErrors = useMemo((): Record<string, string | null> => {
    const errors: Record<string, string | null> = {};
    if (state.formValues === null) {
      return errors;
    }
    for (const spec of FIELD_SPECS) {
      errors[spec.key] = validateField(spec, state.formValues[spec.key]);
    }
    return errors;
  }, [state.formValues]);

  const anyFieldInvalid = useMemo((): boolean => {
    return Object.values(fieldErrors).some((err) => err !== null);
  }, [fieldErrors]);

  const dirty = isDirty(state.serverConfig, state.formValues);

  const handleTextChange = useCallback(
    (key: keyof AdminConfig) =>
      (_ev: ChangeEvent<HTMLInputElement>, data: { value: string }): void => {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: data.value,
        });
      },
    [],
  );

  const handleNumberChange = useCallback(
    (key: keyof AdminConfig) =>
      (_ev: ChangeEvent<HTMLInputElement>, data: { value: string }): void => {
        const parsed = data.value === "" ? Number.NaN : Number(data.value);
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: parsed,
        });
      },
    [],
  );

  const handleSwitchChange = useCallback(
    (key: keyof AdminConfig) =>
      (_ev: ChangeEvent<HTMLInputElement>, data: SwitchOnChangeData): void => {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: data.checked,
        });
      },
    [],
  );

  const handleDiscard = useCallback((): void => {
    dispatch({ type: ConfigActionType.Discard });
  }, []);

  const handleSave = useCallback(async (): Promise<void> => {
    if (state.serverConfig === null || state.formValues === null) {
      return;
    }
    if (anyFieldInvalid) {
      return;
    }
    const patch = computePatch(state.serverConfig, state.formValues);
    dispatch({ type: ConfigActionType.SaveStarted });
    try {
      const runtime = await patchAdminConfig(patch);
      const refreshed = await getAdminConfig();
      dispatch({
        type: ConfigActionType.SaveSucceeded,
        runtime,
        refreshed,
      });
    } catch (err) {
      dispatch({ type: ConfigActionType.SaveFailed, error: errorMessage(err) });
    }
  }, [anyFieldInvalid, state.formValues, state.serverConfig]);

  return (
    <section
      aria-label="configuration"
      data-testid="configuration-page"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Configuration</h2>
        <p className={styles.pageHint}>
          Adjust the runtime-toggle subset of the backend settings.
          Changes persist as overrides on top of the environment
          defaults and live-reload across the running process.
        </p>
      </header>

      <section
        aria-label="runtime configuration"
        data-testid="config-section"
        className={styles.section}
      >
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Runtime settings</h3>
          {state.loadStatus === LoadStatus.Loaded ? (
            <Button
              appearance="secondary"
              onClick={() => {
                void load();
              }}
              disabled={state.saveStatus === SaveStatus.Saving}
              data-testid="config-reload-button"
            >
              Reload
            </Button>
          ) : null}
        </div>

        {state.loadStatus === LoadStatus.Loading ? (
          <p className={styles.statusMessage} data-testid="config-loading">
            Loading configuration…
          </p>
        ) : null}

        {state.loadStatus === LoadStatus.Failed ? (
          <>
            <p className={styles.errorMessage} data-testid="config-load-error">
              {state.loadError ?? "Failed to load configuration."}
            </p>
            <div>
              <Button
                appearance="primary"
                onClick={() => {
                  void load();
                }}
                data-testid="config-load-retry"
              >
                Retry
              </Button>
            </div>
          </>
        ) : null}

        {state.loadStatus === LoadStatus.Loaded && state.formValues !== null
          ? (() => {
              const formValues = state.formValues;
              return (
                <form
                  className={styles.form}
                  data-testid="config-form"
                  onSubmit={(ev) => {
                    ev.preventDefault();
                    void handleSave();
                  }}
                >
                  <div className={styles.fieldGroup}>
                    {FIELD_SPECS.map((spec) => {
                      const value = formValues[spec.key];
                      const fieldError = fieldErrors[spec.key];
                      const inputId = `config-input-${spec.key}`;
                      return (
                        <div
                          key={spec.key}
                          className={styles.field}
                          data-testid={`config-field-${spec.key}`}
                        >
                          <label
                            htmlFor={inputId}
                            className={styles.fieldLabel}
                          >
                            {spec.label}
                            <span className={styles.fieldName}>
                              ({spec.key})
                            </span>
                          </label>
                          {spec.kind === "text" ? (
                            <Input
                              id={inputId}
                              value={value as string}
                              onChange={handleTextChange(spec.key)}
                              disabled={state.saveStatus === SaveStatus.Saving}
                              data-testid={inputId}
                            />
                          ) : null}
                          {spec.kind === "number" ? (
                            <Input
                              id={inputId}
                              type="number"
                              value={
                                typeof value === "number" &&
                                !Number.isNaN(value)
                                  ? value.toString()
                                  : ""
                              }
                              step={spec.numberStep}
                              min={spec.numberMin}
                              max={spec.numberMax}
                              onChange={handleNumberChange(spec.key)}
                              disabled={state.saveStatus === SaveStatus.Saving}
                              data-testid={inputId}
                            />
                          ) : null}
                          {spec.kind === "boolean" ? (
                            <div className={styles.fieldRow}>
                              <Switch
                                id={inputId}
                                checked={value as boolean}
                                onChange={handleSwitchChange(spec.key)}
                                disabled={state.saveStatus === SaveStatus.Saving}
                                data-testid={inputId}
                              />
                              <span>
                                {value === true ? "Enabled" : "Disabled"}
                              </span>
                            </div>
                          ) : null}
                          <p className={styles.fieldHint}>{spec.hint}</p>
                          {fieldError !== null ? (
                            <p
                              className={styles.fieldError}
                              data-testid={`config-field-error-${spec.key}`}
                            >
                              {fieldError}
                            </p>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>

                  {state.saveStatus === SaveStatus.Success ? (
                    <p
                      className={styles.successMessage}
                      data-testid="config-save-status"
                    >
                      Configuration saved.
                    </p>
                  ) : null}
                  {state.saveStatus === SaveStatus.Failed ? (
                    <p
                      className={styles.errorMessage}
                      data-testid="config-save-error"
                    >
                      {state.saveError ?? "Failed to save configuration."}
                    </p>
                  ) : null}

                  {state.lastRuntime !== null ? (
                    <div
                      className={styles.auditFooter}
                      data-testid="config-audit-footer"
                    >
                      <p className={styles.auditLine}>
                        Last updated:{" "}
                        <span className={styles.auditValue}>
                          {formatTimestamp(state.lastRuntime.updated_at)}
                        </span>
                      </p>
                      <p className={styles.auditLine}>
                        Updated by:{" "}
                        <span className={styles.auditValue}>
                          {formatActor(state.lastRuntime.updated_by)}
                        </span>
                      </p>
                    </div>
                  ) : null}

                  <div className={styles.formActions}>
                    <Button
                      type="button"
                      appearance="secondary"
                      onClick={handleDiscard}
                      disabled={!dirty || state.saveStatus === SaveStatus.Saving}
                      data-testid="config-discard-button"
                    >
                      Discard
                    </Button>
                    <Button
                      type="submit"
                      appearance="primary"
                      disabled={
                        !dirty ||
                        anyFieldInvalid ||
                        state.saveStatus === SaveStatus.Saving
                      }
                      data-testid="config-save-button"
                    >
                      {state.saveStatus === SaveStatus.Saving
                        ? "Saving…"
                        : "Save"}
                    </Button>
                  </div>
                </form>
              );
            })()
          : null}
      </section>
    </section>
  );
}
