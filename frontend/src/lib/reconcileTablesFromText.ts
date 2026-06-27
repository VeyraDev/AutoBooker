/**
 * 就地修复 TipTap 文档中的损坏表格，不重建整章。
 * 从章节 Markdown 原文重新解析表格，替换 doc 中对应的 table 节点。
 */

import { markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import {
  normalizeGfmMarkdown,
  tiptapDocHasMessyTables,
  tiptapHasBrokenTable,
} from "@/lib/normalizeGfmMarkdown";

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

function isOrphanTableFragment(node: Record<string, unknown>): boolean {
  if (node.type !== "paragraph") return false;
  const t = extractParagraphText(node);
  if (/^[^|\n]{1,24}\s*\|\s*$/.test(t)) return true;
  if (/^---\s*\|\s*$/.test(t)) return true;
  if (/^\|\s*---/.test(t)) return true;
  return false;
}

function extractTableNodes(doc: Record<string, unknown>): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  const walk = (n: unknown) => {
    if (!n || typeof n !== "object") return;
    const o = n as Record<string, unknown>;
    if (o.type === "table") out.push(o);
    if (Array.isArray(o.content)) o.content.forEach(walk);
  };
  walk(doc);
  return out;
}

/** 仅替换损坏的 table 节点，保留其余段落/标题结构。 */
export function reconcileTablesFromText(
  doc: Record<string, unknown>,
  sourceText: string,
): Record<string, unknown> {
  if (!sourceText.trim() || doc.type !== "doc" || !Array.isArray(doc.content)) return doc;
  if (!tiptapDocHasMessyTables(doc) && !tiptapHasBrokenTable(doc)) return doc;

  try {
    const normalized = normalizeGfmMarkdown(sourceText);
    const fromMd = markdownToTiptapDoc(normalized) as Record<string, unknown>;
    const fixedTables = extractTableNodes(fromMd);
    if (fixedTables.length === 0) return doc;

    let ti = 0;
    const newContent: unknown[] = [];
    for (const node of doc.content as Record<string, unknown>[]) {
      if (!node || typeof node !== "object") continue;
      if (isOrphanTableFragment(node)) continue;
      if (node.type === "table") {
        if (ti < fixedTables.length) newContent.push(fixedTables[ti++]);
        continue;
      }
      newContent.push(node);
    }
    return { ...doc, content: newContent };
  } catch {
    return doc;
  }
}

/** 正文有结构但 tiptap_json 被压成整墙段落（常见于错误的整章重建）。 */
export function tiptapDocCollapsedButTextStructured(
  text: string,
  doc: Record<string, unknown>,
): boolean {
  const s = text.replace(/\r\n/g, "\n");
  const hasStructure =
    /\n\s*\n/.test(s) ||
    /^#{1,6}\s/m.test(s) ||
    /^第[一二三四五六七八九十\d]+节/m.test(s) ||
    /^\s{0,3}\|[^\n]+\|\s*$/m.test(s);
  if (!hasStructure || s.length < 500) return false;

  const content = doc.content as unknown[];
  if (!Array.isArray(content) || content.length === 0) return false;

  let headingCount = 0;
  let blockCount = 0;
  let paraChars = 0;
  for (const node of content) {
    if (!node || typeof node !== "object") continue;
    const o = node as Record<string, unknown>;
    blockCount += 1;
    if (o.type === "heading") headingCount += 1;
    if (o.type === "paragraph") paraChars += extractParagraphText(o).length;
  }

  if (blockCount === 1 && paraChars > 800) return true;
  if (blockCount <= 2 && headingCount === 0 && paraChars > 800 && s.length > paraChars * 1.2) {
    return true;
  }
  return false;
}
