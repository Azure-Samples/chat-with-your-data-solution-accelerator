/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Admin Prompt Editor page. Loads the current effective
 * `cwyd_agent_instructions` via `GET /api/admin/config`, persists
 * operator overrides via `PATCH /api/admin/config`, and exposes a
 * Reset-to-default action that sends `null` (RFC 7396 clear) so the
 * field reverts to the built-in `CWYD_AGENT` instructions.
 *
 * 422 responses whose `detail.field === "cwyd_agent_instructions"`
 * are surfaced as a structured inline RAI rejection; the dirty
 * draft is retained so the operator can revise without re-typing.
 */
import { type JSX, useCallback, useEffect, useState } from "react";
import { Button, Textarea } from "@fluentui/react-components";
import {
  AdminApiError,
  getAdminConfig,
  patchAdminConfig,
} from "@/api/admin";
import { LoadStatus, SaveStatus } from "@/models/status";
import styles from "./PromptEditor.module.css";

const PROMPT_FIELD_KEY = "cwyd_agent_instructions";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function extractRaiRejection(err: unknown): string | null {
  if (!(err instanceof AdminApiError) || err.status !== 422) {
    return null;
  }
  const detail = err.body?.detail;
  if (detail === undefined || typeof detail === "string") {
    return null;
  }
  if (detail.field !== PROMPT_FIELD_KEY) {
    return null;
  }
  return (
    detail.reason ??
    detail.msg ??
    "Safety check rejected the submitted prompt."
  );
}

export function PromptEditor(): JSX.Element {
  const [loadStatus, setLoadStatus] = useState<LoadStatus>(LoadStatus.Loading);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savedPrompt, setSavedPrompt] = useState("");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>(SaveStatus.Idle);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [raiRejection, setRaiRejection] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoadStatus(LoadStatus.Loading);
    setLoadError(null);
    try {
      const config = await getAdminConfig();
      setSavedPrompt(config.cwyd_agent_instructions);
      setDraftPrompt(config.cwyd_agent_instructions);
      setLoadStatus(LoadStatus.Loaded);
    } catch (err) {
      setLoadError(errorMessage(err));
      setLoadStatus(LoadStatus.Failed);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const isDirty = draftPrompt !== savedPrompt;
  const isLoaded = loadStatus === LoadStatus.Loaded;
  const isSaving = saveStatus === SaveStatus.Saving;

  const handleSave = useCallback(async (): Promise<void> => {
    if (!isLoaded || !isDirty || isSaving) {
      return;
    }
    setSaveStatus(SaveStatus.Saving);
    setSaveError(null);
    setRaiRejection(null);
    try {
      await patchAdminConfig({ [PROMPT_FIELD_KEY]: draftPrompt });
      const refreshed = await getAdminConfig();
      setSavedPrompt(refreshed.cwyd_agent_instructions);
      setDraftPrompt(refreshed.cwyd_agent_instructions);
      setSaveStatus(SaveStatus.Success);
    } catch (err) {
      const rejection = extractRaiRejection(err);
      if (rejection !== null) {
        setRaiRejection(rejection);
      } else {
        setSaveError(errorMessage(err));
      }
      setSaveStatus(SaveStatus.Failed);
    }
  }, [draftPrompt, isDirty, isLoaded, isSaving]);

  const handleResetDraft = useCallback((): void => {
    setDraftPrompt(savedPrompt);
    setSaveStatus(SaveStatus.Idle);
    setSaveError(null);
    setRaiRejection(null);
  }, [savedPrompt]);

  const handleResetToDefault = useCallback(async (): Promise<void> => {
    if (!isLoaded || isSaving) {
      return;
    }
    setSaveStatus(SaveStatus.Saving);
    setSaveError(null);
    setRaiRejection(null);
    try {
      await patchAdminConfig({ [PROMPT_FIELD_KEY]: null });
      const refreshed = await getAdminConfig();
      setSavedPrompt(refreshed.cwyd_agent_instructions);
      setDraftPrompt(refreshed.cwyd_agent_instructions);
      setSaveStatus(SaveStatus.Success);
    } catch (err) {
      setSaveError(errorMessage(err));
      setSaveStatus(SaveStatus.Failed);
    }
  }, [isLoaded, isSaving]);

  return (
    <section
      aria-label="prompt editor"
      data-testid="prompt-editor-page"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Prompt editor</h2>
        <p className={styles.pageHint}>
          Override the system prompt used by the primary CWYD agent.
          Save persists the override across the running process;
          Reset to default clears the override and reverts to the
          built-in instructions.
        </p>
      </header>

      <section className={styles.section} data-testid="prompt-editor-form">
        <h3 className={styles.sectionTitle}>System prompt</h3>

        {loadStatus === LoadStatus.Loading ? (
          <p className={styles.statusMessage} data-testid="prompt-loading">
            Loading current prompt...
          </p>
        ) : null}

        {loadStatus === LoadStatus.Failed ? (
          <div
            className={styles.errorMessage}
            data-testid="prompt-load-error"
            role="alert"
          >
            <span>Failed to load prompt: {loadError}</span>
            <Button
              appearance="secondary"
              size="small"
              data-testid="prompt-load-retry"
              onClick={() => {
                void load();
              }}
            >
              Retry
            </Button>
          </div>
        ) : null}

        {raiRejection !== null ? (
          <p
            className={styles.errorMessage}
            data-testid="prompt-rai-error"
            role="alert"
          >
            {raiRejection}
          </p>
        ) : null}

        {saveError !== null ? (
          <p
            className={styles.errorMessage}
            data-testid="prompt-save-error"
            role="alert"
          >
            Failed to save prompt: {saveError}
          </p>
        ) : null}

        {saveStatus === SaveStatus.Success ? (
          <p
            className={styles.successMessage}
            data-testid="prompt-save-success"
          >
            Prompt saved.
          </p>
        ) : null}

        <Textarea
          resize="vertical"
          rows={12}
          data-testid="prompt-editor-textarea"
          placeholder="Enter prompt instructions"
          disabled={!isLoaded}
          value={draftPrompt}
          onChange={(_, data) => {
            setDraftPrompt(data.value);
            if (saveStatus !== SaveStatus.Idle) {
              setSaveStatus(SaveStatus.Idle);
              setSaveError(null);
              setRaiRejection(null);
            }
          }}
        />
        <div className={styles.actions}>
          <Button
            appearance="secondary"
            disabled={!isLoaded || isSaving}
            data-testid="prompt-reset-default"
            onClick={() => {
              void handleResetToDefault();
            }}
          >
            Reset to default
          </Button>
          <Button
            appearance="secondary"
            disabled={!isLoaded || !isDirty || isSaving}
            data-testid="prompt-reset"
            onClick={handleResetDraft}
          >
            Reset
          </Button>
          <Button
            appearance="primary"
            disabled={!isLoaded || !isDirty || isSaving}
            data-testid="prompt-save"
            onClick={() => {
              void handleSave();
            }}
          >
            Save
          </Button>
        </div>
      </section>
    </section>
  );
}
