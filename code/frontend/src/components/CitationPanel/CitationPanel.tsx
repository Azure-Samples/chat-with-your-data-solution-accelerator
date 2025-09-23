import React from "react";
import { Stack } from "@fluentui/react";
import { DismissRegular } from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import styles from "./CitationPanel.module.css";

type CitationPanelProps = {
  activeCitation: any;
  setIsCitationPanelOpen: (flag: boolean) => void;
};

function rewriteCitationUrl(markdownText: string) {
  return markdownText.replace(
    /\[([^\]]+)\]\(([^)]+)\)/,
    (match, title, url) => {
      try {
        const parsed = new URL(url);

        // Take only the last segment of the path
        const filename = parsed.pathname.split('/').pop();
        return `[${title}](/api/files/${filename})`;
      } catch {
        return match; // fallback if URL parsing fails
      }
    }
  );
}

export const CitationPanel: React.FC<CitationPanelProps> = (props) => {
  const { activeCitation, setIsCitationPanelOpen } = props;
  return (
    <Stack.Item className={`${styles.citationPanel} ${styles.mobileStyles}`}>
      <Stack
        horizontal
        className={styles.citationPanelHeaderContainer}
        horizontalAlign="space-between"
        verticalAlign="center"
      >
        <span className={styles.citationPanelHeader}>Citations</span>
        <DismissRegular
          role="button"
          onKeyDown={(e) =>
            e.key === " " || e.key === "Enter"
              ? setIsCitationPanelOpen(false)
              : null
          }
          tabIndex={0}
          className={styles.citationPanelDismiss}
          onClick={() => setIsCitationPanelOpen(false)}
        />
      </Stack>
      <h5
        className={`${styles.citationPanelTitle} ${styles.mobileCitationPanelTitle}`}
      >
        {activeCitation[2]}
      </h5>
      <div
        className={`${styles.citationPanelDisclaimer} ${styles.mobileCitationPanelDisclaimer}`}
      >
        Tables, images, and other special formatting not shown in this preview.
        Please follow the link to review the original document.
      </div>
      <ReactMarkdown
        className="citation-panel"
        children={rewriteCitationUrl(activeCitation[0])}
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      />

    </Stack.Item>
  );
};
