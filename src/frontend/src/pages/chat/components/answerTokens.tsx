/**
 * Pure renderer that turns an assistant-answer string into a mix of
 * raw text spans and clickable `[docN]` citation tokens. The model
 * emits citation markers as bracketed plain text (`[doc1]`, `[doc2]`,
 * …) interleaved with the prose; we tokenize on a fixed regex and
 * promote each marker whose index resolves against the message's
 * `citations` array into a `<button>` that dispatches a focus action
 * back into `<ChatContext>`. Markers that do not resolve -- either
 * because no citation list exists or the index is out of bounds --
 * are rendered verbatim so the wire content is never destroyed.
 *
 * Numbering is 1-based on the wire (the first citation is `[doc1]`)
 * to match the prompt-side convention shared across CWYD orchestrators.
 * `[doc0]` is therefore always out of bounds and renders literally.
 */
import type { ReactNode } from "react";
import type { Citation } from "@/models/chat";
import styles from "./answerTokens.module.css";

const TOKEN_PATTERN = /\[doc(\d+)\]/g;

export function renderAnswerTokens(
  content: string,
  messageId: string,
  citations: Citation[] | undefined,
  onCitationClick: (citationId: string) => void,
): ReactNode {
  if (citations === undefined || citations.length === 0) {
    // No resolvable citations -- render the answer verbatim so any
    // `[docN]` markers stay visible to the user.
    return content;
  }

  const parts: ReactNode[] = [];
  let cursor = 0;
  let nodeKey = 0;
  for (const match of content.matchAll(TOKEN_PATTERN)) {
    const matchIndex = match.index;
    const raw = match[0];
    const oneBasedStr = match[1];
    if (oneBasedStr === undefined) continue;
    const oneBased = Number.parseInt(oneBasedStr, 10);

    // Push any text before this token.
    if (matchIndex > cursor) {
      parts.push(content.slice(cursor, matchIndex));
    }

    const citation =
      oneBased >= 1 && oneBased <= citations.length
        ? citations[oneBased - 1]
        : undefined;

    if (citation === undefined) {
      // Out-of-bounds token -- render verbatim so the user can see
      // the marker the model produced.
      parts.push(raw);
    } else {
      const citationId = citation.id;
      parts.push(
        <button
          key={`tok-${nodeKey}`}
          type="button"
          className={styles.token}
          data-testid={`answer-token-${messageId}-${oneBased}`}
          data-citation-id={citationId}
          onClick={() => {
            onCitationClick(citationId);
          }}
        >
          {raw}
        </button>,
      );
      nodeKey += 1;
    }

    cursor = matchIndex + raw.length;
  }

  // Push any trailing text after the last token.
  if (cursor < content.length) {
    parts.push(content.slice(cursor));
  }

  // No markers matched -- return the original string so React mounts a
  // single text node rather than an array of one.
  if (parts.length === 0) {
    return content;
  }
  return parts;
}
