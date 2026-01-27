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
        const blobStorageHost = 'blob.core.windows.net';

        if (parsed.hostname.includes(blobStorageHost)) {
          // Extract the path after the container name (e.g., /documents/filename or /documents/https://...)
          const pathParts = parsed.pathname.split('/');
          // Remove empty first element and container name, join the rest
          const filenameOrUrl = pathParts.slice(2).join('/');

          // Check if it's a URL (BYOD case where URL is stored as blob path)
          if (filenameOrUrl.startsWith('http://') || filenameOrUrl.startsWith('https://')) {
            console.log('BYOD URL stored in blob - returning as external link');
            return `[${title}](${filenameOrUrl})`;
          }

          return `[${title}](/api/files/${filenameOrUrl})`;
        } else {
          return `[${title}](${parsed.href})`;
        }
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
      <div className="citation-panel">
        <ReactMarkdown
          children={rewriteCitationUrl(activeCitation[0])}
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            a: ({ node, ...props }) => (
              <a {...props} target="_blank" rel="noopener noreferrer" />
            ),
          }}
        />
      </div>

    </Stack.Item>
  );
};
