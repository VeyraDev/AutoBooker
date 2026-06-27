/**
 * 旧章节 tiptap_json 中公式常以纯文本 $$…$$ 存于段落，加载时需迁移为 math 节点。
 */

import { normalizeLatexInput } from "@/lib/latexNormalize";
import { splitInlineMath, tokenizeMathInMarkdown, type MathSegment } from "@/lib/mathTokenizer";
import { tiptapHasNodeType } from "@/lib/buildTiptapDocWithFigures";

const MATH_DELIM_RE =
  /\$\$[\s\S]+?\$\$|(?<!\$)\$(?!\$)[^\$]+?\$(?!\$)|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]/;

export function textHasMathDelimiters(text: string): boolean {
  if (!text?.trim()) return false;
  return MATH_DELIM_RE.test(text.replace(/\r\n/g, "\n"));
}

export function tiptapDocHasMathNodes(doc: Record<string, unknown>): boolean {
  return tiptapHasNodeType(doc, "mathInline") || tiptapHasNodeType(doc, "mathBlock");
}

/** 文档内是否仍有未迁移的公式分隔符（纯 text 节点中的 $…$ / $$…$$）。 */
export function tiptapDocHasRawMathText(doc: Record<string, unknown>): boolean {
  let found = false;

  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "mathInline" || n.type === "mathBlock") return;
    if (n.type === "text" && typeof n.text === "string" && textHasMathDelimiters(n.text)) {
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

function makeMathBlock(latex: string): Record<string, unknown> {
  const norm = normalizeLatexInput(latex, { preferKind: "block" });
  return {
    type: "mathBlock",
    attrs: {
      latex: norm.latex,
      numbered: norm.numbered,
      equationNumber: norm.equationNumber,
      label: norm.label,
    },
  };
}

function makeMathInline(latex: string): Record<string, unknown> {
  return { type: "mathInline", attrs: { latex: normalizeLatexInput(latex).latex } };
}

function segmentsToInlineNodes(segments: MathSegment[], marks?: unknown[]): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  for (const seg of segments) {
    if (seg.kind === "text") {
      if (seg.value) out.push({ type: "text", text: seg.value, ...(marks?.length ? { marks } : {}) });
    } else if (seg.kind === "inline") {
      out.push(makeMathInline(seg.latex));
    }
  }
  return out.length ? out : [{ type: "text", text: "" }];
}

function extractBlockText(node: Record<string, unknown>): string {
  const parts: string[] = [];
  const walk = (n: unknown) => {
    if (!n || typeof n !== "object") return;
    const o = n as Record<string, unknown>;
    if (o.type === "text" && typeof o.text === "string") parts.push(o.text);
    if (Array.isArray(o.content)) o.content.forEach(walk);
  };
  walk(node);
  return parts.join("");
}

function migrateTextBlock(
  node: Record<string, unknown>,
  ctx: { inTable: boolean },
): Record<string, unknown> | Record<string, unknown>[] {
  const plain = extractBlockText(node);
  if (!textHasMathDelimiters(plain)) {
    return {
      ...node,
      content: Array.isArray(node.content)
        ? (node.content as unknown[]).map((c) => migrateNode(c, ctx) as Record<string, unknown>)
        : node.content,
    };
  }

  const blockOnly = plain.match(/^\s*\$\$([\s\S]+)\$\$\s*$/) ?? plain.match(/^\s*\\\[([\s\S]+)\\\]\s*$/);
  if (blockOnly) {
    return makeMathBlock(blockOnly[1]);
  }

  const segments = tokenizeMathInMarkdown(plain);
  const hasBlock = segments.some((s) => s.kind === "block");
  if (!hasBlock) {
    const inlineOnly = segments.filter((s) => s.kind !== "block");
    const content = segmentsToInlineNodes(inlineOnly);
    return { ...node, content };
  }

  const blocks: Record<string, unknown>[] = [];
  let textBuf = "";

  const flushTextParagraph = () => {
    const t = textBuf;
    textBuf = "";
    if (!t.trim()) return;
    const inlineSegs = splitInlineMath(t);
    const hasInlineMath = inlineSegs.some((s) => s.kind === "inline");
    blocks.push({
      type: "paragraph",
      content: hasInlineMath ? segmentsToInlineNodes(inlineSegs) : [{ type: "text", text: t }],
    });
  };

  for (const seg of segments) {
    if (seg.kind === "text") {
      textBuf += seg.value;
    } else if (seg.kind === "inline") {
      textBuf += `$${seg.latex}$`;
    } else if (seg.kind === "block") {
      flushTextParagraph();
      blocks.push(makeMathBlock(seg.latex));
    }
  }
  flushTextParagraph();

  if (blocks.length === 1) return blocks[0];
  return blocks;
}

function migrateNode(node: unknown, ctx: { inTable: boolean } = { inTable: false }): unknown | unknown[] {
  if (!node || typeof node !== "object") return node;
  const n = node as Record<string, unknown>;
  const type = n.type;

  if (type === "table") {
    const content = Array.isArray(n.content)
      ? (n.content as unknown[]).map((c) => migrateNode(c, { inTable: true }))
      : n.content;
    return { ...n, content };
  }

  if (ctx.inTable) {
    return n;
  }

  if (type === "mathInline" || type === "mathBlock") {
    const attrs = { ...((n.attrs as Record<string, unknown>) ?? {}) };
    if (typeof attrs.latex === "string") {
      const norm = normalizeLatexInput(String(attrs.latex), {
        preferKind: type === "mathBlock" ? "block" : "inline",
        keepExistingNumber:
          type === "mathBlock"
            ? {
                numbered: Boolean(attrs.numbered),
                equationNumber: String(attrs.equationNumber ?? ""),
                label: String(attrs.label ?? ""),
              }
            : undefined,
      });
      attrs.latex = norm.latex;
      if (type === "mathBlock" && norm.numbered && !attrs.numbered) {
        attrs.numbered = true;
        if (!attrs.equationNumber) attrs.equationNumber = norm.equationNumber;
        if (!attrs.label) attrs.label = norm.label;
      }
    }
    return { ...n, attrs };
  }

  if (type === "paragraph" || type === "heading") {
    return migrateTextBlock(n, ctx);
  }

  if (Array.isArray(n.content)) {
    const next: unknown[] = [];
    for (const child of n.content) {
      const migrated = migrateNode(child, ctx);
      if (Array.isArray(migrated)) next.push(...migrated);
      else next.push(migrated);
    }
    return { ...n, content: next };
  }

  return n;
}

/** 将文档内纯文本公式迁移为 mathInline / mathBlock 节点。 */
export function migrateMathInTiptapDoc(doc: Record<string, unknown>): Record<string, unknown> {
  if (doc.type !== "doc" || !Array.isArray(doc.content)) return doc;

  const content: unknown[] = [];
  for (const node of doc.content) {
    const migrated = migrateNode(node);
    if (Array.isArray(migrated)) content.push(...migrated);
    else content.push(migrated);
  }
  return { ...doc, content };
}
