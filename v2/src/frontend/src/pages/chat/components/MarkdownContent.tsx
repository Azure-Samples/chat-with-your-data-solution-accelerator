/**
 * Pillar: Stable Core
 * Phase: 6 (visual polish)
 *
 * Renders an assistant-supplied markdown string as HTML. Both the answer
 * body and the reasoning panel feed their text through here so the
 * model's markdown — bold, lists, headings, fenced code, and the
 * GitHub-flavoured extensions (tables, strikethrough, task lists,
 * autolinks) — displays as formatted HTML instead of literal source.
 *
 * Rendering goes through `react-markdown` with `remark-gfm` and no
 * raw-HTML rehype pass (`rehype-raw` is deliberately omitted), so any
 * literal HTML embedded in the model output is escaped rather than
 * mounted as live nodes. Anchor links are forced to open in a new tab
 * with `rel="noreferrer"` so a cited destination cannot reach back into
 * the app through `window.opener`.
 */
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const REMARK_PLUGINS = [remarkGfm];

const COMPONENTS: Components = {
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
};

export function MarkdownContent({
  content,
  className,
}: {
  content: string;
  className?: string | undefined;
}) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
