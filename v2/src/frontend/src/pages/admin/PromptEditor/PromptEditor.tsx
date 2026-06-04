/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Admin Prompt Editor route shell. This unit closes the route-level
 * #35d parity gap by exposing a dedicated Prompt editor page in the
 * React admin navigation without introducing backend changes.
 */
import { type JSX } from "react";
import { useEffect, useState } from "react";
import { Button, Textarea } from "@fluentui/react-components";
import { SaveStatus } from "@/models/status";
import styles from "./PromptEditor.module.css";

const SYSTEM_PROMPT_STORAGE_KEY = "cwyd.admin.promptEditor.systemPrompt";

function getStatusText(status: SaveStatus): string {
  if (status === SaveStatus.Saving) {
    return "Saving local draft...";
  }
  if (status === SaveStatus.Success) {
    return "Saved locally in this browser.";
  }
  if (status === SaveStatus.Failed) {
    return "Unable to save local draft.";
  }
  return "Local draft only. Backend persistence is not wired yet.";
}

export function PromptEditor(): JSX.Element {
  const [savedPrompt, setSavedPrompt] = useState("");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>(SaveStatus.Idle);

  useEffect(() => {
    const storedPrompt = window.localStorage.getItem(SYSTEM_PROMPT_STORAGE_KEY);
    const initialPrompt = storedPrompt ?? "";
    setSavedPrompt(initialPrompt);
    setDraftPrompt(initialPrompt);
  }, []);

  const isDirty = draftPrompt !== savedPrompt;

  function onSave(): void {
    setSaveStatus(SaveStatus.Saving);
    try {
      window.localStorage.setItem(SYSTEM_PROMPT_STORAGE_KEY, draftPrompt);
      setSavedPrompt(draftPrompt);
      setSaveStatus(SaveStatus.Success);
    } catch {
      setSaveStatus(SaveStatus.Failed);
    }
  }

  function onReset(): void {
    setDraftPrompt(savedPrompt);
    setSaveStatus(SaveStatus.Idle);
  }

  return (
    <section
      aria-label="prompt editor"
      data-testid="prompt-editor-page"
      className={styles.page}
    >
      <header className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Prompt editor</h2>
        <p className={styles.pageHint}>
          Authoring surface for prompt templates. Backend persistence is a
          follow-up unit.
        </p>
      </header>

      <section className={styles.section} data-testid="prompt-editor-form">
        <h3 className={styles.sectionTitle}>System prompt</h3>
        <p className={styles.status} data-testid="prompt-status">
          {getStatusText(saveStatus)}
        </p>
        <Textarea
          resize="vertical"
          rows={12}
          data-testid="prompt-editor-textarea"
          placeholder="Enter prompt instructions"
          value={draftPrompt}
          onChange={(_, data) => {
            setDraftPrompt(data.value);
            if (saveStatus !== SaveStatus.Idle) {
              setSaveStatus(SaveStatus.Idle);
            }
          }}
        />
        <div className={styles.actions}>
          <Button
            appearance="secondary"
            disabled={!isDirty}
            data-testid="prompt-reset"
            onClick={onReset}
          >
            Reset
          </Button>
          <Button
            appearance="primary"
            disabled={!isDirty || saveStatus === SaveStatus.Saving}
            data-testid="prompt-save"
            onClick={onSave}
          >
            Save
          </Button>
        </div>
      </section>
    </section>
  );
}
