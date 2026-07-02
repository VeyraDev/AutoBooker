/** 判断章节正文是否实质为空（仅剩 pid 占位或空白段落）。 */

import { stripReviewPidComments } from "@/lib/reviewPidComments";

function stripPidComments(text: string): string {
  return stripReviewPidComments(text).trim();
}

function tiptapPlainLen(node: unknown): number {
  if (!node || typeof node !== "object") return 0;
  const o = node as Record<string, unknown>;
  if (o.type === "text" && typeof o.text === "string") return o.text.trim().length;
  if (Array.isArray(o.content)) {
    return o.content.reduce((s: number, x: unknown) => s + tiptapPlainLen(x), 0);
  }
  return 0;
}

export function isChapterBodyEffectivelyEmpty(
  content: Record<string, unknown> | null | undefined,
): boolean {
  if (!content || typeof content !== "object") return true;
  const text = stripPidComments(typeof content.text === "string" ? content.text : "");
  if (text.length > 40) return false;

  const tj = content.tiptap_json;
  if (!tj || typeof tj !== "object") return text.length === 0;
  const serialized = JSON.stringify(tj);
  if (serialized.includes('"figureBlock"')) return false;
  if (serialized.includes('"heading"') || serialized.includes('"table"')) return false;

  const plain = tiptapPlainLen(tj);
  return plain <= 40;
}
