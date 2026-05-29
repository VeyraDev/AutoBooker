/** 将 LLM 输出的管道表格规范为 GFM（补分隔行、合并被空行拆开的表格行） */

function isTableRow(line: string): boolean {
  const t = line.trim();
  return t.startsWith("|") && t.endsWith("|") && t.length > 2;
}

function isTableSeparator(line: string): boolean {
  const t = line.trim();
  if (!isTableRow(t)) return false;
  return /^\|[\s\-:|]+\|$/.test(t);
}

function splitCells(line: string): string[] {
  let inner = line.trim();
  if (inner.startsWith("|")) inner = inner.slice(1);
  if (inner.endsWith("|")) inner = inner.slice(0, -1);
  return inner.split("|").map((c) => c.trim());
}

function makeSeparator(colCount: number): string {
  const cols = Array.from({ length: Math.max(1, colCount) }, () => "---");
  return `| ${cols.join(" | ")} |`;
}

function ensureTableHeaderSeparator(rows: string[]): string[] {
  if (rows.length === 0) return rows;
  const colCount = splitCells(rows[0]).length;
  if (rows.length === 1) {
    return [rows[0], makeSeparator(colCount)];
  }
  if (!isTableSeparator(rows[1])) {
    return [rows[0], makeSeparator(colCount), ...rows.slice(1)];
  }
  return rows;
}

export function normalizeGfmTables(markdown: string): string {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    if (isTableRow(lines[i])) {
      const tableLines: string[] = [];
      while (i < lines.length) {
        const line = lines[i];
        if (isTableRow(line) || isTableSeparator(line)) {
          tableLines.push(line);
          i += 1;
          continue;
        }
        if (!line.trim() && i + 1 < lines.length && isTableRow(lines[i + 1])) {
          i += 1;
          continue;
        }
        break;
      }
      out.push(ensureTableHeaderSeparator(tableLines).join("\n"));
      continue;
    }
    out.push(lines[i]);
    i += 1;
  }

  return out.join("\n");
}

export function normalizeGfmMarkdown(markdown: string): string {
  return normalizeGfmTables(markdown);
}
