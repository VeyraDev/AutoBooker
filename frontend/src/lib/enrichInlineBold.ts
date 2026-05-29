/** 将段落/单元格内字面量 **加粗** 转为 TipTap bold mark */

function parseInlineBold(text: string): Record<string, unknown>[] {
  if (!text) return [];
  const out: Record<string, unknown>[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push({ type: "text", text: text.slice(last, m.index) });
    }
    out.push({ type: "text", text: m[1], marks: [{ type: "bold" }] });
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    out.push({ type: "text", text: text.slice(last) });
  }
  if (out.length === 0) {
    out.push({ type: "text", text });
  }
  return out;
}

function enrichParagraphContent(content: unknown[] | undefined): unknown[] | undefined {
  if (!Array.isArray(content)) return content;
  const next: unknown[] = [];
  let changed = false;
  for (const child of content) {
    if (!child || typeof child !== "object") {
      next.push(child);
      continue;
    }
    const c = child as Record<string, unknown>;
    if (c.type === "text") {
      const marks = Array.isArray(c.marks) ? c.marks : [];
      const text = String(c.text ?? "");
      if (!marks.length && /\*\*[^*]+\*\*/.test(text)) {
        next.push(...parseInlineBold(text));
        changed = true;
        continue;
      }
    }
    next.push(child);
  }
  return changed ? next : content;
}

function enrichNode(node: unknown): unknown {
  if (!node || typeof node !== "object") return node;
  const n = node as Record<string, unknown>;
  const t = n.type;
  if (t === "paragraph" && Array.isArray(n.content)) {
    const enriched = enrichParagraphContent(n.content as unknown[]);
    if (enriched !== n.content) {
      return { ...n, content: enriched };
    }
  }
  if (Array.isArray(n.content)) {
    return { ...n, content: (n.content as unknown[]).map((child) => enrichNode(child)) };
  }
  return n;
}

export function enrichInlineBoldInDoc(doc: Record<string, unknown>): Record<string, unknown> {
  if (doc.type !== "doc" || !Array.isArray(doc.content)) return doc;
  return {
    ...doc,
    content: (doc.content as unknown[]).map((node) => enrichNode(node)),
  };
}
