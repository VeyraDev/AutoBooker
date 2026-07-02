/** 将 LLM 输出的管道表格规范为 GFM（合并拆行表头、去除重复分隔行、统一列数） */

import { stripReviewPidComments } from "@/lib/reviewPidComments";

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

function formatRow(cells: string[]): string {
  return `| ${cells.join(" | ")} |`;
}

function makeSeparator(colCount: number): string {
  const cols = Array.from({ length: Math.max(1, colCount) }, () => "---");
  return formatRow(cols);
}

function padRow(cells: string[], colCount: number): string[] {
  const row = [...cells];
  while (row.length < colCount) row.push("");
  return row.slice(0, colCount);
}

/** 如「开放程度 |」——被换行拆开的表头单元（必须较短且以 | 结尾） */
function isOrphanHeaderFragment(line: string): boolean {
  const t = line.trim();
  if (!t || isTableRow(t) || isPartialSeparatorLine(t)) return false;
  return /^[^|\n]{1,24}\s*\|\s*$/.test(t);
}

/** 如「--- |」「| --- | --- |」——应丢弃的残缺分隔行 */
function isPartialSeparatorLine(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  if (isTableSeparator(t)) return true;
  if (/^[-—:\s|]+$/.test(t) && t.includes("-")) return true;
  if (/^---\s*\|?\s*$/.test(t)) return true;
  return false;
}

function fragmentToCells(line: string): string[] {
  const t = line.trim();
  if (isTableRow(t)) return splitCells(t);
  let body = t.startsWith("|") ? t.slice(1) : t;
  if (body.endsWith("|")) body = body.slice(0, -1);
  if (body.includes("|")) {
    return body.split("|").map((c) => c.trim()).filter(Boolean);
  }
  return [t.replace(/\|\s*$/, "").trim()];
}

function isDataRow(cells: string[]): boolean {
  if (cells.length === 0) return false;
  if (cells.every((c) => /^[-:\s—]+$/.test(c) || c === "---")) return false;
  if (cells.length >= 2) return true;
  return /^\d+[\d.]*$/.test(cells[0]) || cells[0].length > 12;
}

/** 将一段混杂的表格行修复为规范 GFM 表格 Markdown */
function repairTableBlock(rawLines: string[]): string {
  const lines = rawLines.map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) return "";

  const headerParts: string[][] = [];
  const bodyRows: string[][] = [];
  let seenData = false;

  for (const line of lines) {
    if (isPartialSeparatorLine(line)) continue;

    if (isOrphanHeaderFragment(line)) {
      const cells = fragmentToCells(line);
      if (!seenData) headerParts.push(cells);
      else bodyRows.push(cells);
      continue;
    }

    if (isTableRow(line)) {
      const cells = splitCells(line);
      if (isTableSeparator(line)) continue;
      if (isDataRow(cells)) {
        seenData = true;
        bodyRows.push(cells);
      } else if (!seenData) {
        headerParts.push(cells);
      } else {
        bodyRows.push(cells);
      }
    }
  }

  if (headerParts.length === 0 && bodyRows.length > 0) {
    headerParts.push(bodyRows.shift()!);
  }

  const header = headerParts.flat();
  if (header.length === 0) return rawLines.join("\n");

  const colCount = Math.max(
    header.length,
    ...bodyRows.map((r) => r.length),
  );
  const headerRow = padRow(header, colCount);
  const out = [formatRow(headerRow), makeSeparator(colCount)];
  for (const row of bodyRows) {
    out.push(formatRow(padRow(row, colCount)));
  }
  return out.join("\n");
}

function isOrphanPipeLine(line: string): boolean {
  const t = line.trim();
  return t === "|" || t === "- |";
}

function dropOrphanPipeLines(lines: string[]): string[] {
  return lines.filter((line) => !isOrphanPipeLine(line));
}

function isTableRelatedLine(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  return isTableRow(t) || isOrphanHeaderFragment(t) || isPartialSeparatorLine(t);
}

function collectTableRegion(lines: string[], start: number): { end: number; block: string[] } {
  const block: string[] = [];
  let i = start;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j += 1;
      if (j < lines.length && isTableRelatedLine(lines[j])) {
        i = j;
        continue;
      }
      break;
    }
    if (block.length === 0) {
      if (!isTableRelatedLine(line)) break;
      block.push(line);
      i += 1;
      continue;
    }
    if (!isTableRelatedLine(line)) break;
    block.push(line);
    i += 1;
  }
  return { end: i, block };
}

export function normalizeGfmTables(markdown: string): string {
  const lines = dropOrphanPipeLines(
    stripReviewPidComments(markdown).replace(/\r\n/g, "\n").split("\n"),
  );
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const nextRelated =
      i + 1 < lines.length && isTableRelatedLine(lines[i + 1]);
    if (isTableRow(line) || (isOrphanHeaderFragment(line) && nextRelated)) {
      const { end, block } = collectTableRegion(lines, i);
      if (block.length > 0) {
        out.push(repairTableBlock(block));
        i = end;
        continue;
      }
    }
    out.push(line);
    i += 1;
  }

  return out.join("\n");
}

export function normalizeGfmMarkdown(markdown: string): string {
  return normalizeGfmTables(markdown);
}

/** 统计 Markdown 文本中的表格数据行数（不含分隔行） */
export function countMarkdownTableDataRows(markdown: string): number {
  const normalized = normalizeGfmTables(markdown.replace(/\r\n/g, "\n"));
  let count = 0;
  let inTable = false;
  let seenSep = false;
  for (const line of normalized.split("\n")) {
    if (isTableRow(line)) {
      if (!inTable) {
        inTable = true;
        seenSep = false;
        continue;
      }
      if (isTableSeparator(line)) {
        seenSep = true;
        continue;
      }
      if (seenSep) count += 1;
      continue;
    }
    inTable = false;
    seenSep = false;
  }
  return count;
}

function extractCellText(cell: Record<string, unknown>): string {
  const parts: string[] = [];
  const walk = (node: unknown) => {
    if (!node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "text" && typeof n.text === "string") parts.push(n.text);
    if (Array.isArray(n.content)) n.content.forEach(walk);
  };
  walk(cell);
  return parts.join(" ").trim();
}

function extractParagraphText(node: Record<string, unknown>): string {
  const parts: string[] = [];
  const walk = (n: unknown) => {
    if (!n || typeof n !== "object") return;
    const o = n as Record<string, unknown>;
    if (o.type === "text" && typeof o.text === "string") parts.push(o.text);
    if (Array.isArray(o.content)) o.content.forEach(walk);
  };
  walk(node);
  return parts.join("").trim();
}

function rowLooksLikeSeparator(cells: Record<string, unknown>[]): boolean {
  if (cells.length === 0) return false;
  return cells.every((cell) => /^[-:\s—]+$/.test(extractCellText(cell)) || extractCellText(cell) === "---");
}

export function tiptapHasBrokenTable(doc: Record<string, unknown>): boolean {
  let broken = false;

  function walk(node: unknown) {
    if (broken || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "table" && Array.isArray(n.content)) {
      const rows = (n.content as unknown[]).filter(
        (r) => r && typeof r === "object" && (r as Record<string, unknown>).type === "tableRow",
      ) as Record<string, unknown>[];
      if (rows.length > 0) {
        const firstCells = ((rows[0].content as unknown[]) ?? []).filter(
          (c) =>
            c &&
            typeof c === "object" &&
            ["tableCell", "tableHeader"].includes(String((c as Record<string, unknown>).type)),
        ) as Record<string, unknown>[];
        if (rowLooksLikeSeparator(firstCells)) {
          broken = true;
          return;
        }
      }
    }
    if (Array.isArray(n.content)) {
      for (const child of n.content) walk(child);
    }
  }

  walk(doc);
  return broken;
}

/** 文档顶层是否含表格碎片段落（开放程度 |）或连续多个残缺表格 */
export function tiptapDocHasMessyTables(doc: Record<string, unknown>): boolean {
  if (doc.type !== "doc" || !Array.isArray(doc.content)) return false;
  const nodes = doc.content as Record<string, unknown>[];

  for (const n of nodes) {
    if (n.type === "paragraph") {
      const t = extractParagraphText(n);
      if (/^[^|\n]{1,24}\s*\|\s*$/.test(t)) return true;
      if (/^---\s*\|\s*$/.test(t)) return true;
      if (/^\|\s*---/.test(t)) return true;
    }
  }

  let prevWasTable = false;
  for (const n of nodes) {
    if (n.type === "table") {
      if (prevWasTable) return true;
      prevWasTable = true;
      const rows = ((n.content as unknown[]) ?? []).filter(
        (r) => r && typeof r === "object" && (r as Record<string, unknown>).type === "tableRow",
      ) as Record<string, unknown>[];
      for (const row of rows) {
        const cells = ((row.content as unknown[]) ?? []).filter(
          (c) =>
            c &&
            typeof c === "object" &&
            ["tableCell", "tableHeader"].includes(String((c as Record<string, unknown>).type)),
        ) as Record<string, unknown>[];
        if (rowLooksLikeSeparator(cells)) return true;
      }
    } else {
      prevWasTable = false;
    }
  }
  return false;
}

/** 从已损坏的 TipTap 文档拼回粗略 Markdown，再经 normalize 修复 */
export function roughMarkdownFromDoc(doc: Record<string, unknown>): string {
  if (doc.type !== "doc" || !Array.isArray(doc.content)) return "";
  const parts: string[] = [];

  for (const node of doc.content as Record<string, unknown>[]) {
    if (!node || typeof node !== "object") continue;
    if (node.type === "paragraph" || node.type === "heading") {
      const t = extractParagraphText(node);
      if (t) parts.push(t);
      continue;
    }
    if (node.type === "table") {
      const rows = ((node.content as unknown[]) ?? []).filter(
        (r) => r && typeof r === "object" && (r as Record<string, unknown>).type === "tableRow",
      ) as Record<string, unknown>[];
      for (const row of rows) {
        const cells = ((row.content as unknown[]) ?? []).filter(
          (c) =>
            c &&
            typeof c === "object" &&
            ["tableCell", "tableHeader"].includes(String((c as Record<string, unknown>).type)),
        ) as Record<string, unknown>[];
        const texts = cells.map((c) => extractCellText(c));
        if (texts.some(Boolean)) parts.push(formatRow(texts));
      }
      parts.push("");
    }
  }
  return parts.join("\n");
}

export function textHasMarkdownTable(text: string): boolean {
  return /^\s{0,3}\|[^\n]+\|\s*$/m.test(text.replace(/\r\n/g, "\n"));
}

export function needsTableRebuild(text: string, doc: Record<string, unknown> | null): boolean {
  if (doc && tiptapDocHasMessyTablesOrBroken(doc)) return true;
  if (!textHasMarkdownTable(text)) return false;
  if (!doc) return true;
  if (tiptapHasBrokenTable(doc)) return true;
  const mdRows = countMarkdownTableDataRows(text);
  const tjRows = countTiptapTableDataRows(doc);
  return mdRows > 0 && tjRows < mdRows;
}

function countTiptapTableDataRows(doc: Record<string, unknown>): number {
  let count = 0;
  function walk(node: unknown) {
    if (!node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "table" && Array.isArray(n.content)) {
      const rows = (n.content as unknown[]).filter(
        (r) => r && typeof r === "object" && (r as Record<string, unknown>).type === "tableRow",
      ) as Record<string, unknown>[];
      for (let ri = 1; ri < rows.length; ri += 1) {
        const cells = ((rows[ri].content as unknown[]) ?? []).filter(
          (c) =>
            c &&
            typeof c === "object" &&
            ["tableCell", "tableHeader"].includes(String((c as Record<string, unknown>).type)),
        ) as Record<string, unknown>[];
        if (!rowLooksLikeSeparator(cells)) count += 1;
      }
      return;
    }
    if (Array.isArray(n.content)) n.content.forEach(walk);
  }
  walk(doc);
  return count;
}

export function tiptapDocHasMessyTablesOrBroken(doc: Record<string, unknown>): boolean {
  return tiptapHasBrokenTable(doc) || tiptapDocHasMessyTables(doc);
}
