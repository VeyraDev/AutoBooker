import { generateJSON } from "@tiptap/html";
import { marked } from "marked";

import { chapterEditorSchemaExtensions } from "@/lib/chapterEditorExtensions";
import { mathMarkdownToHtml } from "@/lib/mathMarkdown";
import { normalizeGfmMarkdown } from "@/lib/normalizeGfmMarkdown";
import { shouldParseAsMarkdown } from "@/lib/plainTextMarkdownToTiptap";

marked.setOptions({ gfm: true });

/** 是否值得走 Markdown→HTML→TipTap（表格、代码块、有序列表等） */
export function isRichMarkdown(text: string): boolean {
  if (shouldParseAsMarkdown(text)) return true;
  const s = text.replace(/\r\n/g, "\n");
  if (/```/.test(s)) return true;
  if (/^\s{0,3}\|[^\n]+\|\s*$/m.test(s)) return true;
  if (/(^|\n)\s*\d+\.\s+\S/.test(s)) return true;
  if (/(^|\n)\s*>\s/.test(s)) return true;
  if (/\$\$[\s\S]+?\$\$/.test(s) || /(?<!\$)\$(?!\$)[^\$]+?\$(?!\$)/.test(s)) return true;
  return false;
}

export function markdownToTiptapDoc(markdown: string): Record<string, unknown> {
  const normalized = normalizeGfmMarkdown(markdown);
  const withMath = mathMarkdownToHtml(normalized);
  const html = marked.parse(withMath, { async: false }) as string;
  return generateJSON(html, chapterEditorSchemaExtensions) as Record<string, unknown>;
}
