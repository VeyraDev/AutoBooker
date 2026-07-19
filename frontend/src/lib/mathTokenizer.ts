/** 从 Markdown 文本中识别 LaTeX 公式分隔符（跳过代码块/行内代码）。 */

import { normalizeInlineLatexWhitespace } from "@/lib/latexNormalize";

export type MathSegment =
  | { kind: "text"; value: string }
  | { kind: "inline"; latex: string }
  | { kind: "block"; latex: string };

type Zone = "text" | "fenced" | "inline_code";

function isEscaped(src: string, index: number): boolean {
  let bs = 0;
  let i = index - 1;
  while (i >= 0 && src[i] === "\\") {
    bs += 1;
    i -= 1;
  }
  return bs % 2 === 1;
}

function readUntil(src: string, start: number, endSeq: string): { end: number; found: boolean } {
  let i = start;
  while (i < src.length) {
    if (src.startsWith(endSeq, i) && !isEscaped(src, i)) {
      return { end: i + endSeq.length, found: true };
    }
    i += 1;
  }
  return { end: src.length, found: false };
}

function readSingleLineInlineDollar(src: string, start: number): { latex: string; end: number } | null {
  if (src[start] !== "$" || src[start + 1] === "$") return null;
  let i = start + 1;
  while (i < src.length) {
    const ch = src[i];
    if (ch === "$" && !isEscaped(src, i)) {
      const latex = normalizeInlineLatexWhitespace(src.slice(start + 1, i).trim());
      if (!latex) return null;
      return { latex, end: i + 1 };
    }
    i += 1;
  }
  return null;
}

function readParenInline(src: string, start: number): { latex: string; end: number } | null {
  if (!src.startsWith("\\(", start)) return null;
  const { end, found } = readUntil(src, start + 2, "\\)");
  if (!found) return null;
  const latex = normalizeInlineLatexWhitespace(src.slice(start + 2, end - 2).trim());
  if (!latex) return null;
  return { latex, end };
}

function readBracketBlock(src: string, start: number): { latex: string; end: number } | null {
  if (!src.startsWith("\\[", start)) return null;
  const { end, found } = readUntil(src, start + 2, "\\]");
  if (!found) return null;
  const latex = src.slice(start + 2, end - 2).trim();
  if (!latex) return null;
  return { latex, end };
}

function readDoubleDollarBlock(src: string, start: number): { latex: string; end: number } | null {
  if (!src.startsWith("$$", start)) return null;
  const { end, found } = readUntil(src, start + 2, "$$");
  if (!found) return null;
  const latex = src.slice(start + 2, end - 2).trim();
  if (!latex) return null;
  return { latex, end };
}

/** 对单段普通文本做行内公式切分。 */
export function splitInlineMath(text: string): MathSegment[] {
  const out: MathSegment[] = [];
  let i = 0;
  let buf = "";
  const flush = () => {
    if (buf) {
      out.push({ kind: "text", value: buf });
      buf = "";
    }
  };
  while (i < text.length) {
    const paren = readParenInline(text, i);
    if (paren) {
      flush();
      out.push({ kind: "inline", latex: paren.latex });
      i = paren.end;
      continue;
    }
    const dollar = readSingleLineInlineDollar(text, i);
    if (dollar) {
      flush();
      out.push({ kind: "inline", latex: dollar.latex });
      i = dollar.end;
      continue;
    }
    buf += text[i];
    i += 1;
  }
  flush();
  return out.length ? out : [{ kind: "text", value: text }];
}

/** 将 Markdown 切分为文本块、行内公式与独立公式块。 */
export function tokenizeMathInMarkdown(markdown: string): MathSegment[] {
  const src = (markdown || "").replace(/\r\n/g, "\n");
  const out: MathSegment[] = [];
  let zone: Zone = "text";
  let fence: string | null = null;
  let i = 0;
  let buf = "";

  const flushText = () => {
    if (!buf) return;
    // 行内 $...$ 留给段落解析；此处只切 block 级公式。
    out.push({ kind: "text", value: buf });
    buf = "";
  };

  while (i < src.length) {
    if (zone === "fenced") {
      const lineEnd = src.indexOf("\n", i);
      const line = lineEnd === -1 ? src.slice(i) : src.slice(i, lineEnd);
      const trimmed = line.trim();
      if (trimmed === fence) {
        out.push({ kind: "text", value: buf + line + (lineEnd === -1 ? "" : "\n") });
        buf = "";
        zone = "text";
        fence = null;
        i = lineEnd === -1 ? src.length : lineEnd + 1;
        continue;
      }
      buf += line + (lineEnd === -1 ? "" : "\n");
      i = lineEnd === -1 ? src.length : lineEnd + 1;
      continue;
    }

    if (zone === "inline_code") {
      if (src[i] === "`" && !isEscaped(src, i)) {
        buf += "`";
        i += 1;
        zone = "text";
        continue;
      }
      buf += src[i];
      i += 1;
      continue;
    }

    if (src.startsWith("```", i)) {
      flushText();
      fence = "```";
      zone = "fenced";
      buf = "```";
      i += 3;
      continue;
    }

    if (src[i] === "`" && !isEscaped(src, i)) {
      flushText();
      zone = "inline_code";
      buf = "`";
      i += 1;
      continue;
    }

    const bracket = readBracketBlock(src, i);
    if (bracket) {
      flushText();
      out.push({ kind: "block", latex: bracket.latex });
      i = bracket.end;
      continue;
    }

    const dblock = readDoubleDollarBlock(src, i);
    if (dblock) {
      flushText();
      out.push({ kind: "block", latex: dblock.latex });
      i = dblock.end;
      continue;
    }

    buf += src[i];
    i += 1;
  }

  if (zone === "fenced") {
    out.push({ kind: "text", value: buf });
  } else {
    flushText();
  }
  return out.length ? out : [{ kind: "text", value: "" }];
}

export function escapeHtmlAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** 生成仅含 data-latex 的占位 HTML（不含 KaTeX DOM，供 generateJSON 解析）。 */
export function mathSegmentsToPlaceholderHtml(segments: MathSegment[]): string {
  return segments
    .map((seg) => {
      if (seg.kind === "text") return seg.value;
      const escaped = escapeHtmlAttr(seg.latex);
      if (seg.kind === "block") {
        return `<div data-type="math-block" data-latex="${escaped}"></div>`;
      }
      return `<span data-type="math-inline" data-latex="${escaped}"></span>`;
    })
    .join("");
}
