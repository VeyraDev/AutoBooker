import { ANNOTATION_FULL_RE, FIGURE_CAPTION_LINE_RE } from "@/lib/annotationPatterns";
import { isRichMarkdown, markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import { plainTextMarkdownToTiptapDoc } from "@/lib/plainTextMarkdownToTiptap";
import { normalizeGfmMarkdown } from "@/lib/normalizeGfmMarkdown";

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
  const trimmed = normalizeGfmMarkdown(segment).trim();
  if (!trimmed) return [];
  const doc = isRichMarkdown(trimmed)
    ? markdownToTiptapDoc(trimmed)
    : plainTextMarkdownToTiptapDoc(trimmed);
  const content = doc.content;
  if (!Array.isArray(content)) return [];
  return content.filter((n): n is Record<string, unknown> => !!n && typeof n === "object");
}

function mergeFigureCaption(block: Record<string, unknown>, caption: string): Record<string, unknown> {
  if (!caption) return block;
  const attrs = { ...((block.attrs as Record<string, unknown>) ?? {}) };
  attrs.caption = caption;
  return { ...block, attrs };
}

function placeholderFigureBlock(rawAnnotation: string): Record<string, unknown> {
  return {
    type: "figureBlock",
    attrs: {
      figureId: "",
      figureType: "figure",
      figureNumber: "",
      caption: rawAnnotation.slice(0, 200),
      status: "pending",
      fileUrl: "",
      svgUrl: "",
      rawAnnotation,
    },
  };
}

function parseAnnotationTag(full: string): { figureType: string; raw: string } {
  const inner = full.slice(1, -1);
  const colon = inner.indexOf(":");
  const tag = colon >= 0 ? inner.slice(0, colon).trim().toUpperCase() : "FIGURE";
  const raw = colon >= 0 ? inner.slice(colon + 1).trim() : inner;
  const figureType =
    tag === "FLOWCHART"
      ? "flowchart"
      : tag === "CHART"
        ? "chart"
        : tag === "SCREENSHOT"
          ? "screenshot"
          : "figure";
  return { figureType, raw };
}

/**
 * 用章节 Markdown 原文 + 图表块列表构建 TipTap 文档，保留标题、表格、公式、加粗等结构。
 */
export function buildTiptapDocWithFigures(
  markdownText: string,
  figureBlocks: Record<string, unknown>[],
): Record<string, unknown> {
  const content: Record<string, unknown>[] = [];
  let figIdx = 0;
  let cursor = 0;
  const re = new RegExp(ANNOTATION_FULL_RE.source, "g");

  for (const m of markdownText.matchAll(re)) {
    const start = m.index ?? 0;
    content.push(...markdownSegmentToBlocks(markdownText.slice(cursor, start)));

    let figBlock =
      figIdx < figureBlocks.length ? figureBlocks[figIdx] : placeholderFigureBlock("");
    if (!(figIdx < figureBlocks.length)) {
      const { figureType, raw } = parseAnnotationTag(m[0]);
      const attrs = (figBlock.attrs as Record<string, unknown>) ?? {};
      figBlock = {
        ...figBlock,
        attrs: { ...attrs, figureType, rawAnnotation: raw, caption: raw.slice(0, 200) },
      };
    }

    let after = start + m[0].length;
    const rest = markdownText.slice(after);
    const firstLine = rest.split("\n")[0]?.trim() ?? "";
    const capMatch = FIGURE_CAPTION_LINE_RE.exec(firstLine);
    if (capMatch) {
      figBlock = mergeFigureCaption(figBlock, capMatch[3].trim());
      attrsPatchFigureNumber(figBlock, capMatch[1], capMatch[2]);
      after += firstLine.length + (rest.startsWith("\n") ? 1 : 0);
    }

    content.push(figBlock);
    figIdx += 1;
    cursor = after;
  }

  content.push(...markdownSegmentToBlocks(markdownText.slice(cursor)));

  if (!content.length) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }
  return { type: "doc", content };
}

function attrsPatchFigureNumber(block: Record<string, unknown>, ch: string, seq: string) {
  const attrs = (block.attrs as Record<string, unknown>) ?? {};
  attrs.figureNumber = `${ch}-${seq}`;
  block.attrs = attrs;
}

/** 文档是否仍含标题、表格等富文本结构 */
export function tiptapHasRichStructure(doc: Record<string, unknown>): boolean {
  let found = false;

  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    const type = n.type;
    if (
      type === "heading" ||
      type === "table" ||
      type === "bulletList" ||
      type === "orderedList" ||
      type === "codeBlock" ||
      type === "blockquote" ||
      type === "figureBlock" ||
      type === "mathBlock" ||
      type === "mathInline"
    ) {
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

export function tiptapHasNodeType(doc: Record<string, unknown>, nodeType: string): boolean {
  let found = false;

  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === nodeType) {
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

/** text 含代码块/表格/有序列表，但 tiptap_json 未保留对应节点（常见于 sync 后的简陋文档） */
export function tiptapMissingMarkdownFeatures(
  text: string,
  doc: Record<string, unknown>,
): boolean {
  const s = text.replace(/\r\n/g, "\n");
  if (/```/.test(s) && !tiptapHasNodeType(doc, "codeBlock")) return true;
  if (/^\s{0,3}\|[^\n]+\|\s*$/m.test(s) && !tiptapHasNodeType(doc, "table")) return true;
  if (/(^|\n)\s*\d+\.\s+\S/.test(s) && !tiptapHasNodeType(doc, "orderedList")) return true;
  return false;
}

export function tiptapHasFigureBlocks(doc: Record<string, unknown>): boolean {
  let found = false;
  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "figureBlock") {
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

export function countAnnotationsInMarkdown(text: string): number {
  return [...text.matchAll(new RegExp(ANNOTATION_FULL_RE.source, "g"))].length;
}

/** 将 sync 接口的简陋文档升级为保留 Markdown 排版的完整文档 */
export function enrichSyncedTiptapDoc(
  markdownText: string,
  syncDoc: Record<string, unknown>,
): Record<string, unknown> {
  const figureBlocks = extractFigureBlocksFromDoc(syncDoc);
  if (!markdownText.trim()) {
    return syncDoc;
  }
  return buildTiptapDocWithFigures(markdownText, figureBlocks);
}
