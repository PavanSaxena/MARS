import ReactMarkdown from "react-markdown";

const LIST_ITEM_RE = /^[ \t]*(?:[-*+]|\d+[.)])[ \t]+/;
const FENCE_RE = /^[ \t]*(```|~~~)/;

/**
 * LLM output often puts a blank line between list items (or between a
 * bullet's intro line and its nested sub-list). That's valid markdown, but
 * remark treats it as a "loose" list and wraps every item's text in <p>,
 * which then stacks paragraph + list margins into big gaps between bullets.
 * ChatGPT-style rendering wants tight lists, so we drop a blank line
 * whenever it sits directly between two list-item lines (skipping fenced
 * code blocks, where blank lines are meaningful).
 */
function tightenLists(text) {
  const lines = text.split("\n");
  const out = [];
  let inFence = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (FENCE_RE.test(line)) inFence = !inFence;

    if (!inFence && line.trim() === "") {
      const prev = out.length ? out[out.length - 1] : "";
      let j = i + 1;
      while (j < lines.length && lines[j].trim() === "") j++;
      const next = j < lines.length ? lines[j] : "";
      if (LIST_ITEM_RE.test(prev) && LIST_ITEM_RE.test(next)) {
        continue; // drop this blank line, keep the list tight
      }
    }

    out.push(line);
  }

  return out.join("\n");
}

/**
 * Renders LLM-authored markdown (bold, lists, headings, code, etc.) with the
 * app's typography instead of dumping raw "**text**" on screen. `inline`
 * strips block-level wrapping (used for short list items).
 */
export default function Markdown({ children, inline = false }) {
  if (!children) return null;

  return (
    <div className={`md ${inline ? "md-inline" : ""}`}>
      <ReactMarkdown
        components={
          inline
            ? {
                // Render a single paragraph's children with no <p> wrapper,
                // so it sits inline inside a <li>/badge instead of forcing
                // a block-level break.
                p: ({ children }) => <>{children}</>,
              }
            : undefined
        }
      >
        {tightenLists(children)}
      </ReactMarkdown>
    </div>
  );
}
