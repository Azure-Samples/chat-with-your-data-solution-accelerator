/**
 * Admin "Configuration" page. Surfaces the runtime-toggle subset
 * of `AppSettings` plus `RuntimeConfig`-only fields (e.g. the
 * post-answering validator trio) and lets the operator patch any
 * subset of those fields via RFC 7396 JSON Merge Patch.
 *
 * One section, four first-class states (no thrown exception ever
 * reaches the user):
 *
 * 1. **Loading** -- on mount and on Retry, `getAdminConfig()` is
 *    fired and the form is replaced with a status message.
 * 2. **Failed** -- the wire call rejected; the error message is
 *    surfaced and a Retry button re-fires the GET.
 * 3. **Loaded (clean)** -- the inputs render the effective server
 *    values; Save / Discard are disabled until the operator edits
 *    a field.
 * 4. **Loaded (dirty)** -- Save and Discard become active. Save
 *    PATCHes only the changed fields (RFC 7396 absent-key
 *    semantics: untouched fields stay untouched server-side).
 *
 * A "Reset to default" control sits alongside Save / Discard.
 * Behind a destructive-confirm dialog it clears every override at
 * once (an all-null merge patch) and re-syncs the form to the
 * resolved environment + built-in defaults.
 *
 * Per-field client-side validation (number bounds, non-empty
 * strings on fields that disallow it) keeps invalid edits out of
 * the wire; the typed client already enforces a server-side 422
 * ladder for anything that slips past. A 422 carrying a structured
 * `detail.field` payload for a RAI-guarded field is surfaced
 * inline beside the offending row instead of in the generic
 * save-error banner.
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
import {
  Button,
  Input,
  Label,
  Select,
  Switch,
  Textarea,
} from "@fluentui/react-components";
import type {
  SwitchOnChangeData,
  TextareaOnChangeData,
} from "@fluentui/react-components";
import { Info16Regular } from "@fluentui/react-icons";
import {
  AdminApiError,
  getAdminConfig,
  getAssistantTypePresets,
  patchAdminConfig,
  resetAdminConfig,
} from "@/api/admin";
import { AssistantType, LogLevel, OrchestratorName } from "@/models/admin";
import type {
  AdminConfig,
  AdminConfigPatch,
  AssistantTypePresets,
  RuntimeConfig,
} from "@/models/admin";
import {
  LoadStatus,
  SaveStatus,
} from "@/models/status";
import styles from "./Configuration.module.css";

/**
 * The subset of `AdminConfig` keys that render as inline knob rows
 * on the configuration page. The closed list is kept explicit so it
 * never silently drifts when `AdminConfig` grows -- any new writable
 * field must be added here in lockstep with the wire model and the
 * backend `WRITABLE_FIELDS` allow-list.
 */
type ConfigFieldKey =
  | "orchestrator_name"
  | "openai_temperature"
  | "openai_max_tokens"
  | "search_use_semantic_search"
  | "search_top_k"
  | "log_level"
  | "content_safety_enabled"
  | "ai_assistant_type"
  | "cwyd_agent_instructions"
  | "post_answering_prompt"
  | "post_answering_enabled"
  | "post_answering_filter_message";

/**
 * One row in the inline configuration form. `key` is the wire-shape
 * field name and must match `AdminConfig` + the backend
 * `WRITABLE_FIELDS` allow-list verbatim.
 *
 * `multiline` upgrades the renderer for `text` fields from `<Input>`
 * to `<Textarea>` so a prompt template gets line-wrapped editing.
 * `allowEmpty` opts a `text` field out of the non-empty validation
 * guard -- needed for fields whose empty value carries semantic
 * meaning at the server (e.g. "validator disabled" or "fall back to
 * the built-in default").
 *
 * `options` supplies the closed set of choices for a `select` field,
 * rendered as a dropdown instead of a free-text input.
 */
interface FieldSpec {
  key: ConfigFieldKey;
  label: string;
  hint: string;
  tooltip: string;
  kind: "text" | "number" | "boolean" | "select";
  multiline?: boolean;
  allowEmpty?: boolean;
  numberStep?: string;
  numberMin?: number;
  numberMax?: number;
  options?: readonly string[];
}

/**
 * Wire-field keys whose 422 rejections may carry a structured
 * `detail.field` payload from the backend RAI gate. Used by
 * `extractRaiRejection` to render the rejection inline next to the
 * offending row instead of as a generic save error banner.
 */
const RAI_GUARDED_FIELDS: ReadonlySet<ConfigFieldKey> = new Set<ConfigFieldKey>([
  "cwyd_agent_instructions",
  "post_answering_prompt",
]);

/**
 * Parse an `AdminApiError` into a `(field, message)` pair when the
 * 422 body carries a structured RAI rejection for one of the
 * RAI-guarded fields above. Returns `null` for anything else --
 * non-`AdminApiError`, non-422, string-shaped detail, or a field
 * key the page doesn't render -- so the caller falls back to the
 * generic save-error banner.
 */
function extractRaiRejection(
  err: unknown,
): { field: ConfigFieldKey; message: string } | null {
  if (!(err instanceof AdminApiError) || err.status !== 422) {
    return null;
  }
  const detail = err.body?.detail;
  if (detail === undefined || typeof detail === "string") {
    return null;
  }
  const field = detail.field;
  if (
    field === undefined ||
    !RAI_GUARDED_FIELDS.has(field as ConfigFieldKey)
  ) {
    return null;
  }
  return {
    field: field as ConfigFieldKey,
    message:
      detail.reason ??
      detail.msg ??
      "Safety check rejected the submitted value.",
  };
}

const FIELD_SPECS: readonly FieldSpec[] = [
  {
    key: "ai_assistant_type",
    label: "Assistant type",
    hint: "Switch between the default, contract, and employee personas. Selecting one loads its prompt into the System prompt field below, where you can edit it before saving.",
    tooltip:
      "Choose which persona preset the assistant answers under: the default assistant, the Contract Assistant, or the Employee (HR) Assistant. Selecting one loads its prompt into the System prompt field below, which you can still edit before saving.",
    kind: "select",
    options: [
      AssistantType.Default,
      AssistantType.Contract,
      AssistantType.Employee,
    ],
  },
  {
    key: "cwyd_agent_instructions",
    label: "System prompt",
    hint: "System prompt for the primary assistant. Leave empty to fall back to the built-in default prompt.",
    tooltip:
      "The system persona the assistant answers under. Sources are retrieved and cited automatically by the orchestrator, so this is behavioral instructions only -- no {sources} or {question} placeholders are needed. Leave empty to fall back to the built-in default prompt.",
    kind: "text",
    multiline: true,
    allowEmpty: true,
  },
  {
    key: "orchestrator_name",
    label: "Orchestrator",
    hint: "Registry key of the active orchestrator (e.g. langgraph, agent_framework).",
    tooltip:
      "The orchestration engine that runs the chat pipeline. Swappable through the backend provider registry; the built-in choices are langgraph and agent_framework.",
    kind: "select",
    options: [OrchestratorName.LangGraph, OrchestratorName.AgentFramework],
  },
  {
    key: "openai_temperature",
    label: "OpenAI temperature",
    hint: "Sampling temperature for the chat model. 0.0 = deterministic, 2.0 = maximally random.",
    tooltip:
      "Sampling temperature for the chat model. Lower values (near 0.0) make answers more focused and deterministic; higher values (toward 2.0) make them more varied and creative.",
    kind: "number",
    numberStep: "0.05",
    numberMin: 0,
    numberMax: 2,
  },
  {
    key: "openai_max_tokens",
    label: "OpenAI max tokens",
    hint: "Maximum number of tokens the chat model may generate per response.",
    tooltip:
      "Upper bound on the number of tokens the chat model may generate in a single response. Higher values allow longer answers but cost more per call.",
    kind: "number",
    numberStep: "1",
    numberMin: 1,
  },
  {
    key: "search_use_semantic_search",
    label: "Use semantic search",
    hint: "Enable Azure AI Search semantic reranking on retrieval queries.",
    tooltip:
      "Enable Azure AI Search semantic reranking on retrieval queries, reordering retrieved chunks by relevance for higher-quality grounding.",
    kind: "boolean",
  },
  {
    key: "search_top_k",
    label: "Search top K",
    hint: "Number of chunks to retrieve per query before reranking.",
    tooltip:
      "How many document chunks to retrieve per query before reranking. Larger values widen the grounding context at the cost of more tokens.",
    kind: "number",
    numberStep: "1",
    numberMin: 1,
  },
  {
    key: "log_level",
    label: "Log level",
    hint: "Python logging level for the backend process (DEBUG, INFO, WARNING, ERROR).",
    tooltip:
      "Verbosity of the backend process logs. DEBUG is the most detailed; ERROR is the quietest. Affects the running process via live-reload.",
    kind: "select",
    options: [LogLevel.Debug, LogLevel.Info, LogLevel.Warning, LogLevel.Error],
  },
  {
    key: "content_safety_enabled",
    label: "Content safety",
    hint: "Enable the Azure AI Content Safety pre-filter on user input.",
    tooltip:
      "Screen user input through Azure AI Content Safety before it reaches the model, blocking messages that breach the configured harm categories.",
    kind: "boolean",
  },
  {
    key: "post_answering_enabled",
    label: "Post-answering validator",
    hint: "Run the post-answering groundedness check on every assistant response. Requires a non-empty prompt below to take effect.",
    tooltip:
      "Run a second groundedness check on every assistant response. This adds an extra model call per answer and can replace ungrounded answers with the filter message below, so enable it deliberately. Requires the post-answering prompt below.",
    kind: "boolean",
  },
  {
    key: "post_answering_prompt",
    label: "Post-answering prompt",
    hint: "Prompt template the validator sends back to the LLM. Use {question}, {answer}, and {sources} placeholders. Leave empty to disable the validator regardless of the toggle above.",
    tooltip:
      "You can configure a post prompt that allows to fact-check or process the answer, given the sources, question and answer. This prompt needs to return True or False.",
    kind: "text",
    multiline: true,
    allowEmpty: true,
  },
  {
    key: "post_answering_filter_message",
    label: "Post-answering filter message",
    hint: "Reply returned to the user when the validator rejects an answer as ungrounded. Leave empty to fall back to the built-in default message.",
    tooltip:
      "The message that is returned to the user, when the post-answering prompt returns.",
    kind: "text",
    allowEmpty: true,
  },
] as const;

type FieldValue = string | number | boolean;
type FormValues = Record<ConfigFieldKey, FieldValue>;

interface ConfigurationState {
  loadStatus: LoadStatus;
  loadError: string | null;
  serverConfig: AdminConfig | null;
  formValues: FormValues | null;
  saveStatus: SaveStatus;
  saveError: string | null;
  raiRejection: { field: ConfigFieldKey; message: string } | null;
  lastRuntime: RuntimeConfig | null;
  assistantTypePresets: AssistantTypePresets;
  resetConfirmOpen: boolean;
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
  ResetRequested: "reset_requested",
  ResetCancelled: "reset_cancelled",
} as const;
export type ConfigActionType =
  (typeof ConfigActionType)[keyof typeof ConfigActionType];

type ConfigurationAction =
  | { type: typeof ConfigActionType.LoadStarted }
  | {
      type: typeof ConfigActionType.LoadSucceeded;
      config: AdminConfig;
      presets: AssistantTypePresets;
    }
  | { type: typeof ConfigActionType.LoadFailed; error: string }
  | {
      type: typeof ConfigActionType.FieldChanged;
      key: ConfigFieldKey;
      value: FieldValue;
    }
  | { type: typeof ConfigActionType.Discard }
  | { type: typeof ConfigActionType.SaveStarted }
  | {
      type: typeof ConfigActionType.SaveSucceeded;
      runtime: RuntimeConfig;
      refreshed: AdminConfig;
    }
  | {
      type: typeof ConfigActionType.SaveFailed;
      error: string;
      raiRejection: { field: ConfigFieldKey; message: string } | null;
    }
  | { type: typeof ConfigActionType.ResetRequested }
  | { type: typeof ConfigActionType.ResetCancelled };

const initialState: ConfigurationState = {
  loadStatus: LoadStatus.Loading,
  loadError: null,
  serverConfig: null,
  formValues: null,
  saveStatus: SaveStatus.Idle,
  saveError: null,
  raiRejection: null,
  lastRuntime: null,
  assistantTypePresets: {},
  resetConfirmOpen: false,
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
    ai_assistant_type: config.ai_assistant_type,
    cwyd_agent_instructions: config.cwyd_agent_instructions,
    post_answering_prompt: config.post_answering_prompt,
    post_answering_enabled: config.post_answering_enabled,
    post_answering_filter_message: config.post_answering_filter_message,
  };
}

/** Wire strings of the closed `AssistantType` set. */
const ASSISTANT_TYPE_VALUES: readonly string[] = Object.values(AssistantType);

/**
 * Coalesce a missing or unknown `ai_assistant_type` to the default
 * preset so the Assistant-type dropdown always lands on a real option
 * rather than an empty phantom entry. Applied where the server config
 * enters reducer state so `serverConfig` and `formValues` agree (no
 * spurious dirty state).
 */
function withAssistantTypeDefault(config: AdminConfig): AdminConfig {
  return ASSISTANT_TYPE_VALUES.includes(config.ai_assistant_type)
    ? config
    : { ...config, ai_assistant_type: AssistantType.Default };
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
        raiRejection: null,
        resetConfirmOpen: false,
      };
    case ConfigActionType.LoadSucceeded: {
      const loadedConfig = withAssistantTypeDefault(action.config);
      return {
        loadStatus: LoadStatus.Loaded,
        loadError: null,
        serverConfig: loadedConfig,
        formValues: configToForm(loadedConfig),
        saveStatus: SaveStatus.Idle,
        saveError: null,
        raiRejection: null,
        lastRuntime: state.lastRuntime,
        assistantTypePresets: action.presets,
        resetConfirmOpen: false,
      };
    }
    case ConfigActionType.LoadFailed:
      return {
        ...state,
        loadStatus: LoadStatus.Failed,
        loadError: action.error,
        serverConfig: null,
        formValues: null,
        resetConfirmOpen: false,
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
        raiRejection:
          state.raiRejection !== null && state.raiRejection.field === action.key
            ? null
            : state.raiRejection,
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
        raiRejection: null,
      };
    case ConfigActionType.SaveStarted:
      return {
        ...state,
        saveStatus: SaveStatus.Saving,
        saveError: null,
        raiRejection: null,
        resetConfirmOpen: false,
      };
    case ConfigActionType.SaveSucceeded: {
      const refreshedConfig = withAssistantTypeDefault(action.refreshed);
      return {
        loadStatus: LoadStatus.Loaded,
        loadError: null,
        serverConfig: refreshedConfig,
        formValues: configToForm(refreshedConfig),
        saveStatus: SaveStatus.Success,
        saveError: null,
        raiRejection: null,
        lastRuntime: action.runtime,
        assistantTypePresets: state.assistantTypePresets,
        resetConfirmOpen: false,
      };
    }
    case ConfigActionType.SaveFailed:
      return {
        ...state,
        saveStatus: SaveStatus.Failed,
        saveError: action.raiRejection === null ? action.error : null,
        raiRejection: action.raiRejection,
      };
    case ConfigActionType.ResetRequested:
      return { ...state, resetConfirmOpen: true };
    case ConfigActionType.ResetCancelled:
      return { ...state, resetConfirmOpen: false };
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
      case "cwyd_agent_instructions":
        patch.cwyd_agent_instructions = after as string;
        break;
      case "ai_assistant_type":
        patch.ai_assistant_type = after as string;
        break;
      case "post_answering_prompt":
        patch.post_answering_prompt = after as string;
        break;
      case "post_answering_enabled":
        patch.post_answering_enabled = after as boolean;
        break;
      case "post_answering_filter_message":
        patch.post_answering_filter_message = after as string;
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
    if (typeof value !== "string") {
      return `${spec.label} cannot be empty.`;
    }
    if (spec.allowEmpty !== true && value.trim().length === 0) {
      return `${spec.label} cannot be empty.`;
    }
    return null;
  }
  if (spec.kind === "select") {
    if (typeof value !== "string" || value.trim().length === 0) {
      return `${spec.label} must be selected.`;
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
      const [config, presets] = await Promise.all([
        getAdminConfig(),
        getAssistantTypePresets(),
      ]);
      dispatch({ type: ConfigActionType.LoadSucceeded, config, presets });
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
    (key: ConfigFieldKey) =>
      (_ev: ChangeEvent<HTMLInputElement>, data: { value: string }): void => {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: data.value,
        });
      },
    [],
  );

  const handleSelectChange = useCallback(
    (key: ConfigFieldKey) =>
      (_ev: ChangeEvent<HTMLSelectElement>, data: { value: string }): void => {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: data.value,
        });
      },
    [],
  );

  const handleAssistantTypeChange = useCallback(
    (_ev: ChangeEvent<HTMLSelectElement>, data: { value: string }): void => {
      dispatch({
        type: ConfigActionType.FieldChanged,
        key: "ai_assistant_type",
        value: data.value,
      });
      const presetBody = state.assistantTypePresets[data.value];
      if (presetBody !== undefined) {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key: "cwyd_agent_instructions",
          value: presetBody,
        });
      }
    },
    [state.assistantTypePresets],
  );

  const handleTextareaChange = useCallback(
    (key: ConfigFieldKey) =>
      (
        _ev: ChangeEvent<HTMLTextAreaElement>,
        data: TextareaOnChangeData,
      ): void => {
        dispatch({
          type: ConfigActionType.FieldChanged,
          key,
          value: data.value,
        });
      },
    [],
  );

  const handleNumberChange = useCallback(
    (key: ConfigFieldKey) =>
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
    (key: ConfigFieldKey) =>
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
      dispatch({
        type: ConfigActionType.SaveFailed,
        error: errorMessage(err),
        raiRejection: extractRaiRejection(err),
      });
    }
  }, [anyFieldInvalid, state.formValues, state.serverConfig]);

  const handleResetRequest = useCallback((): void => {
    dispatch({ type: ConfigActionType.ResetRequested });
  }, []);

  const handleResetCancel = useCallback((): void => {
    dispatch({ type: ConfigActionType.ResetCancelled });
  }, []);

  const handleResetConfirm = useCallback(async (): Promise<void> => {
    dispatch({ type: ConfigActionType.SaveStarted });
    try {
      const runtime = await resetAdminConfig();
      const refreshed = await getAdminConfig();
      dispatch({
        type: ConfigActionType.SaveSucceeded,
        runtime,
        refreshed,
      });
    } catch (err) {
      dispatch({
        type: ConfigActionType.SaveFailed,
        error: errorMessage(err),
        raiRejection: extractRaiRejection(err),
      });
    }
  }, []);

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
                      const selectOptions: readonly string[] =
                        spec.kind === "select"
                          ? (spec.options ?? []).includes(value as string)
                            ? (spec.options ?? [])
                            : [value as string, ...(spec.options ?? [])]
                          : [];
                      return (
                        <div
                          key={spec.key}
                          className={styles.field}
                          data-testid={`config-field-${spec.key}`}
                        >
                          <div className={styles.fieldLabel}>
                            <Label htmlFor={inputId}>{spec.label}</Label>
                            <span className={styles.infoWrapper}>
                              <Button
                                type="button"
                                appearance="transparent"
                                size="small"
                                icon={<Info16Regular />}
                                aria-label={spec.tooltip}
                              />
                              <span className={styles.infoPopup} role="tooltip">
                                {spec.tooltip}
                              </span>
                            </span>
                          </div>
                          {spec.kind === "text" && spec.multiline === true ? (
                            <Textarea
                              id={inputId}
                              value={value as string}
                              onChange={handleTextareaChange(spec.key)}
                              disabled={state.saveStatus === SaveStatus.Saving}
                              data-testid={inputId}
                              rows={6}
                              resize="vertical"
                            />
                          ) : null}
                          {spec.kind === "text" && spec.multiline !== true ? (
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
                          {spec.kind === "select" ? (
                            <Select
                              id={inputId}
                              value={value as string}
                              onChange={
                                spec.key === "ai_assistant_type"
                                  ? handleAssistantTypeChange
                                  : handleSelectChange(spec.key)
                              }
                              disabled={state.saveStatus === SaveStatus.Saving}
                              data-testid={inputId}
                            >
                              {selectOptions.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </Select>
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
                          {state.raiRejection !== null &&
                          state.raiRejection.field === spec.key ? (
                            <p
                              className={styles.fieldError}
                              data-testid={`config-field-rai-${spec.key}`}
                            >
                              {state.raiRejection.message}
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
                  {state.saveStatus === SaveStatus.Failed &&
                  state.raiRejection === null ? (
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
                      className={styles.resetButton}
                      onClick={handleResetRequest}
                      disabled={state.saveStatus === SaveStatus.Saving}
                      data-testid="config-reset-button"
                    >
                      Reset to default
                    </Button>
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

        {state.resetConfirmOpen ? (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Confirm reset"
            data-testid="config-reset-dialog"
            className={styles.dialogBackdrop}
          >
            <div className={styles.dialog}>
              <h3 className={styles.dialogTitle}>Reset to default?</h3>
              <p className={styles.dialogBody}>
                This clears every saved configuration override and restores
                the environment and built-in defaults (including the default
                orchestrator and system prompt). Any unsaved edits are also
                discarded. This action cannot be undone.
              </p>
              <div className={styles.dialogActions}>
                <Button
                  type="button"
                  appearance="secondary"
                  onClick={handleResetCancel}
                  data-testid="config-reset-cancel-button"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  appearance="primary"
                  onClick={() => {
                    void handleResetConfirm();
                  }}
                  data-testid="config-reset-confirm-button"
                >
                  Reset to default
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </section>
  );
}
