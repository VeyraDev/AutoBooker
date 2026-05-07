/**
 * 将常见 Markdown 纯文本转为 TipTap JSON：标题 #～###、无序列表 - / *、**加粗**。
 */

export function shouldParseAsMarkdown(text: string): boolean {
  const s = text.replace(/\r\n/g, "\n");
  if (/(^|\n)\s*#{1,3}(\s|\u3000|\S)/.test(s)) return true;
  if (/\*\*[^*]+\*\*/.test(s)) return true;
  if (/(^|\n)\s*[-*]\s+\S/.test(s)) return true;
  return false;
}

function parseInlineBoldAndText(t: string): Record<string, unknown>[] {
  if (!t) return [];
  const out: Record<string, unknown>[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(t)) !== null) {
    if (m.index > last) {
      out.push({ type: "text", text: t.slice(last, m.index) });
    }
    out.push({ type: "text", text: m[1], marks: [{ type: "bold" }] });
    last = m.index + m[0].length;
  }
  if (last < t.length) {
    out.push({ type: "text", text: t.slice(last) });
  }
  if (out.length === 0) {
    out.push({ type: "text", text: t });
  }
  return out;
}

function isBulletLine(line: string): boolean {
  return /^\s*[-*]\s+/.test(line);
}

export function plainTextMarkdownToTiptapDoc(text: string): Record<string, unknown> {
  const normalized = text.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const blocks: Record<string, unknown>[] = [];
  const paraLines: string[] = [];
  const bulletLines: string[] = [];

  function flushBulletList() {
    if (bulletLines.length === 0) return;
    blocks.push({
      type: "bulletList",
      content: bulletLines.map((raw) => {
        const itemText = raw.replace(/^\s*[-*]\s+/, "").trim();
        return {
          type: "listItem",
          content: [
            {
              type: "paragraph",
              content: parseInlineBoldAndText(itemText),
            },
          ],
        };
      }),
    });
    bulletLines.length = 0;
  }

  function flushParagraphOnly() {
    const t = paraLines.join("\n").trimEnd();
    paraLines.length = 0;
    if (!t.trim()) return;
    blocks.push({
      type: "paragraph",
      content: parseInlineBoldAndText(t),
    });
  }

  for (const line of lines) {
    if (!line.trim()) {
      flushParagraphOnly();
      flushBulletList();
      continue;
    }

    const trim = line.trimStart();
    if (trim.startsWith("###")) {
      flushParagraphOnly();
      flushBulletList();
      const title = trim.slice(3).replace(/^\s+/, "").trim();
      blocks.push({
        type: "heading",
        attrs: { level: 3 },
        content: parseInlineBoldAndText(title),
      });
      continue;
    }
    if (trim.startsWith("##")) {
      flushParagraphOnly();
      flushBulletList();
      const title = trim.slice(2).replace(/^\s+/, "").trim();
      blocks.push({
        type: "heading",
        attrs: { level: 2 },
        content: parseInlineBoldAndText(title),
      });
      continue;
    }
    if (trim.startsWith("#")) {
      flushParagraphOnly();
      flushBulletList();
      const title = trim.slice(1).replace(/^\s+/, "").trim();
      blocks.push({
        type: "heading",
        attrs: { level: 1 },
        content: parseInlineBoldAndText(title),
      });
      continue;
    }

    if (isBulletLine(line)) {
      flushParagraphOnly();
      bulletLines.push(line);
      continue;
    }

    flushBulletList();
    paraLines.push(line);
  }

  flushParagraphOnly();
  flushBulletList();

  if (blocks.length === 0) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }
  return { type: "doc", content: blocks };
}
