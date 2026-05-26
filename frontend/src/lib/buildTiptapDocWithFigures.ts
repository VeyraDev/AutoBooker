import { isRichMarkdown, markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import { plainTextMarkdownToTiptapDoc } from "@/lib/plainTextMarkdownToTiptap";

const ANNOTATION_RE = /\[(?:FLOWCHART|CHART|FIGURE|SCREENSHOT):\s*.*?\]/gsi;

/** 从 sync 接口返回的「简陋」TipTap 文档中提取 figureBlock 节点（保留 figureId 等 attrs） */
export function extractFigureBlocksFromDoc(doc: Record<string, unknown>): Record<string, unknown>[] {
  const blocks: Record<string, unknown>[] = [];

  function walk(node: unknown) {
    if (!node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "figureBlock") {
      blocks.push(n);
      return;
    }
    const children = n.content;
    if (Array.isArray(children)) {
      for (const child of children) walk(child);
    }
  }

  walk(doc);
  return blocks;
}

function markdownSegmentToBlocks(segment: string): Record<string, unknown>[] {
  const trimmed = segment.trim();
  if (!trimmed) return [];
  const doc = isRichMarkdown(trimmed)
    ? markdownToTiptapDoc(trimmed)
    : plainTextMarkdownToTiptapDoc(trimmed);
  const content = doc.content;
  if (!Array.isArray(content)) return [];
  return content.filter((n): n is Record<string, unknown> => !!n && typeof n === "object");
}

/**
 * 用章节 Markdown 原文 + 图表块列表构建 TipTap 文档，保留标题、表格、加粗等结构。
 */
export function buildTiptapDocWithFigures(
  markdownText: string,
  figureBlocks: Record<string, unknown>[],
): Record<string, unknown> {
  const content: Record<string, unknown>[] = [];
  let figIdx = 0;
  let last = 0;

  for (const m of markdownText.matchAll(ANNOTATION_RE)) {
    const start = m.index ?? 0;
    const segment = markdownText.slice(last, start);
    content.push(...markdownSegmentToBlocks(segment));
    if (figIdx < figureBlocks.length) {
      content.push(figureBlocks[figIdx]);
      figIdx += 1;
    }
    last = start + m[0].length;
  }

  content.push(...markdownSegmentToBlocks(markdownText.slice(last)));

  if (!content.length) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }
  return { type: "doc", content };
}

/** 文档是否仍含标题、表格等富文本结构 */
export function tiptapHasRichStructure(doc: Record<string, unknown>): boolean {
  let found = false;

  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    const type = n.type;
    if (type === "heading" || type === "table" || type === "bulletList" || type === "orderedList") {
      found = true;
      return;
    }
    if (Array.isArray(n.content)) {
      for (const child of n.content) walk(child);
    }
  }

  walk(doc);
  return found;
}

/** 将 sync 接口的简陋文档升级为保留 Markdown 排版的完整文档 */
export function enrichSyncedTiptapDoc(
  markdownText: string,
  syncDoc: Record<string, unknown>,
): Record<string, unknown> {
  const figureBlocks = extractFigureBlocksFromDoc(syncDoc);
  if (!figureBlocks.length) {
    return syncDoc;
  }
  if (!markdownText.trim()) {
    return syncDoc;
  }
  return buildTiptapDocWithFigures(markdownText, figureBlocks);
}
