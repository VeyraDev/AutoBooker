/** 审校段落锚点 `<!-- pid:... -->` 的处理（勿插入 GFM 表格行内）。 */

export const PID_COMMENT_RE = /<!--\s*pid:[^>]+-->\s*/gi;

const PID_COMMENT_LINE_RE = /^\s*<!--\s*pid:[^>]+-->\s*$/;

/** 空列表项导出为 `- <!-- pid -->\n- \n`；去 pid 后变成 `- -`，会撑出大量空白。 */
export const EMPTY_PID_LIST_PAIR_RE = /- <!--\s*pid:[^>]+-->\s*\n- \s*\n/gi;

export function stripReviewPidComments(markdown: string): string {
  return (markdown || "").replace(PID_COMMENT_RE, "");
}

/** 移除空 pid 列表项对（须在 strip pid 之前调用）。 */
export function repairEmptyPidListPairs(markdown: string): string {
  return (markdown || "").replace(EMPTY_PID_LIST_PAIR_RE, "");
}

/** strip pid 后仍可能残留的 `- -` / 空 `-` 行。 */
export function dropSpuriousDashListLines(markdown: string): string {
  const lines = (markdown || "").replace(/\r\n/g, "\n").split("\n");
  const dashDash = lines.filter((l) => /^- -\s*$/.test(l.trim())).length;
  if (dashDash < 5) return markdown;
  return lines
    .filter((l) => !/^- -\s*$/.test(l.trim()) && !/^-\s*$/.test(l.trim()))
    .join("\n");
}

/** 表格单元格被 pid 注释拆成多行后，会出现大量孤立的 `|` / `-` 行。 */
export function markdownHasPidTableCorruption(text: string): boolean {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  let orphanPipes = 0;
  let pidLines = 0;
  for (const line of lines) {
    const t = line.trim();
    if (PID_COMMENT_LINE_RE.test(line)) pidLines += 1;
    if (t === "|" || t === "- |" || t === "| --- |" || /^\|\s*---\s*\|?\s*$/.test(t)) {
      orphanPipes += 1;
    }
  }
  return pidLines > 5 && orphanPipes > 15;
}

export function markdownHasEmptyPidListCorruption(text: string): boolean {
  const matches = (text || "").match(EMPTY_PID_LIST_PAIR_RE);
  return (matches?.length ?? 0) > 20;
}

export function markdownHasReviewPidCorruption(text: string): boolean {
  return markdownHasPidTableCorruption(text) || markdownHasEmptyPidListCorruption(text);
}

function tiptapNodePlainLen(node: unknown): number {
  if (!node || typeof node !== "object") return 0;
  const o = node as Record<string, unknown>;
  if (o.type === "text" && typeof o.text === "string") return o.text.trim().length;
  if (Array.isArray(o.content)) {
    return o.content.reduce((s: number, c: unknown) => s + tiptapNodePlainLen(c), 0);
  }
  return 0;
}

/** tiptap_json 被解析成大量无正文 listItem（典型：8893 个空项）。 */
export function tiptapHasSpuriousEmptyLists(doc: Record<string, unknown> | null | undefined): boolean {
  if (!doc || doc.type !== "doc") return false;
  let listItems = 0;
  let emptyListItems = 0;

  const walk = (node: unknown) => {
    if (!node || typeof node !== "object") return;
    const o = node as Record<string, unknown>;
    if (o.type === "listItem") {
      listItems += 1;
      if (tiptapNodePlainLen(o) === 0) emptyListItems += 1;
    }
    if (Array.isArray(o.content)) o.content.forEach(walk);
  };
  walk(doc);

  return listItems > 50 && emptyListItems > listItems * 0.8;
}
