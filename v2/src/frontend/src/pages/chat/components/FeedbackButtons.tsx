/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Presentational thumbs-up / thumbs-down + inline reason picker for a
 * single assistant message. Pure UI -- no fetch, no dispatch, no
 * routing decisions. The parent (`MessageList` in Unit 4) owns the
 * `setFeedback()` API call and the `set_feedback` reducer dispatch;
 * this component just renders the buttons + reason form and bubbles
 * the user's chosen feedback string up via `onSubmit`.
 *
 * Selected-state contract: the "currently set" thumb renders the
 * Fluent v9 Filled icon variant and reports `aria-pressed="true"`
 * via Fluent's `<ToggleButton>` `checked` prop. The component reads
 * the persisted state from the `feedback` prop:
 *   - `feedback === "positive"`             → 👍 is selected.
 *   - `feedback?.startsWith("negative")`    → 👎 is selected.
 * Any other string (or `null` / `undefined`) renders both buttons
 * unselected. Clicking the already-selected thumb is a no-op since
 * the backend has no clear-feedback endpoint today.
 *
 * Negative-flow UX: clicking an unselected 👎 toggles an inline
 * reason form open (textarea + Cancel + Send). Send submits
 * `"negative: <reason>"` when the reason is non-empty, or bare
 * `"negative"` when blank, then collapses the form. The textarea is
 * soft-capped at 53 chars so `"negative: " + reason` fits inside the
 * backend's 64-char body limit (`SetFeedbackRequest.feedback` in
 * v2/src/backend/models/history.py); the hard limit is enforced by
 * the backend returning 422.
 */
import { useState, type SyntheticEvent, type JSX } from "react";
import { Button, ToggleButton } from "@fluentui/react-components";
import {
  ThumbDislike16Filled,
  ThumbDislike16Regular,
  ThumbLike16Filled,
  ThumbLike16Regular,
} from "@fluentui/react-icons";
import styles from "./FeedbackButtons.module.css";

const POSITIVE_VALUE = "positive";
const NEGATIVE_PREFIX = "negative";
const REASON_MAX = 53;

export interface FeedbackButtonsProps {
  messageId: string;
  feedback?: string | null;
  onSubmit: (feedback: string) => Promise<void> | void;
  disabled?: boolean;
}

function isPositive(feedback: string | null | undefined): boolean {
  return feedback === POSITIVE_VALUE;
}

function isNegative(feedback: string | null | undefined): boolean {
  return typeof feedback === "string" && feedback.startsWith(NEGATIVE_PREFIX);
}

export function FeedbackButtons({
  messageId,
  feedback,
  onSubmit,
  disabled = false,
}: FeedbackButtonsProps): JSX.Element {
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState("");

  const positive = isPositive(feedback);
  const negative = isNegative(feedback);

  async function handlePositive(): Promise<void> {
    if (positive || disabled) return;
    setShowReason(false);
    setReason("");
    await onSubmit(POSITIVE_VALUE);
  }

  function handleNegative(): void {
    if (negative || disabled) return;
    setShowReason((prev) => !prev);
    if (showReason) setReason("");
  }

  async function handleReasonSubmit(
    event: SyntheticEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    const trimmed = reason.trim();
    const value =
      trimmed.length > 0
        ? `${NEGATIVE_PREFIX}: ${trimmed}`
        : NEGATIVE_PREFIX;
    setShowReason(false);
    setReason("");
    await onSubmit(value);
  }

  function handleReasonCancel(): void {
    setShowReason(false);
    setReason("");
  }

  return (
    <div className={styles.root} data-testid={`feedback-${messageId}`}>
      <div className={styles.buttons}>
        <ToggleButton
          appearance="subtle"
          shape="circular"
          size="small"
          checked={positive}
          onClick={() => {
            void handlePositive();
          }}
          disabled={disabled}
          aria-label="Good response"
          title="Good response"
          data-testid={`feedback-${messageId}-positive`}
          icon={positive ? <ThumbLike16Filled /> : <ThumbLike16Regular />}
        />
        <ToggleButton
          appearance="subtle"
          shape="circular"
          size="small"
          checked={negative}
          onClick={handleNegative}
          disabled={disabled}
          aria-label="Bad response"
          title="Bad response"
          data-testid={`feedback-${messageId}-negative`}
          icon={
            negative ? <ThumbDislike16Filled /> : <ThumbDislike16Regular />
          }
        />
      </div>
      {showReason && (
        <form
          className={styles.reason}
          onSubmit={(e) => {
            void handleReasonSubmit(e);
          }}
          data-testid={`feedback-${messageId}-reason-form`}
        >
          <label
            htmlFor={`feedback-${messageId}-reason-input`}
            className={styles.reasonLabel}
          >
            What went wrong? (optional)
          </label>
          <textarea
            id={`feedback-${messageId}-reason-input`}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            maxLength={REASON_MAX}
            rows={2}
            className={styles.reasonInput}
            data-testid={`feedback-${messageId}-reason-input`}
          />
          <div className={styles.reasonActions}>
            <Button
              appearance="subtle"
              size="small"
              type="button"
              onClick={handleReasonCancel}
              data-testid={`feedback-${messageId}-reason-cancel`}
            >
              Cancel
            </Button>
            <Button
              appearance="primary"
              size="small"
              type="submit"
              data-testid={`feedback-${messageId}-reason-submit`}
            >
              Send
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
