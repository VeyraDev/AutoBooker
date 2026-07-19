/** Normalize model-generated Markdown before rendering or persistence. */

const HR_LINE = /^\s*(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$/;
const BLOCKQUOTE_PREFIX = /^(\s*)(?:>|＞|&gt;)\s?/;
const KEEP_BRACKET_TAG = /^\[(DIAGRAM|SCREENSHOT|FLOWCHART|CHART)\s*:/i;
const BRACKET_TITLE = /^[\[【]([^\[\]【】]{1,120})[\]】]\s*$/;
const MARKDOWN_BRACKET_HEADING = /^(\s*#{1,6}\s+)[\[【]([^\[\]【】]{1,120})[\]】](\s*)$/;
const NUMERIC_REFERENCE = /^\d+(?:\s*[-,，]\s*\d+)*$/;

export function sanitizeChapterMarkdown(raw: string): string {
  const text = (raw || "").replace(/\r\n/g, "\n");
  const out: string[] = [];
  for (const line of text.split("\n")) {
    if (HR_LINE.test(line)) {
      out.push("");
      continue;
    }
    let cleaned = line;
    while (BLOCKQUOTE_PREFIX.test(cleaned)) {
      cleaned = cleaned.replace(BLOCKQUOTE_PREFIX, "$1");
    }
    const stripped = cleaned.trim();
    if (stripped && !KEEP_BRACKET_TAG.test(stripped)) {
      const headingMatch = cleaned.match(MARKDOWN_BRACKET_HEADING);
      const titleMatch = stripped.match(BRACKET_TITLE);
      if (headingMatch && !NUMERIC_REFERENCE.test(headingMatch[2].trim())) {
        cleaned = `${headingMatch[1]}${headingMatch[2].trim()}${headingMatch[3]}`;
      } else if (titleMatch && !NUMERIC_REFERENCE.test(titleMatch[1].trim())) {
        cleaned = titleMatch[1].trim();
      } else {
        cleaned = cleaned.replace(/\[\s*\]/g, "");
      }
    }
    out.push(cleaned);
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n");
}

/** Remove model-only quote/divider nodes from already-persisted TipTap content. */
export function sanitizeTiptapChapterDoc(
  doc: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!doc || typeof doc !== "object") return doc ?? null;

  const walk = (node: unknown): unknown[] => {
    if (!node || typeof node !== "object") return [node];
    const current = node as Record<string, unknown>;
    if (current.type === "horizontalRule") return [];
    if (current.type === "blockquote") {
      return Array.isArray(current.content) ? current.content.flatMap(walk) : [];
    }
    if (current.type === "text" && typeof current.text === "string") {
      return [{ ...current, text: sanitizeChapterMarkdown(current.text) }];
    }
    if (Array.isArray(current.content)) {
      return [{ ...current, content: current.content.flatMap(walk) }];
    }
    return [current];
  };

  const cleaned = walk(doc)[0];
  return cleaned && typeof cleaned === "object"
    ? (cleaned as Record<string, unknown>)
    : { type: "doc", content: [{ type: "paragraph" }] };
}
