import { figureBlockToAnnotation } from "@/lib/migrateTiptapDoc";

function inlineToMd(nodes: unknown[] | undefined): string {
  if (!Array.isArray(nodes)) return "";
  let out = "";
  for (const n of nodes) {
    if (!n || typeof n !== "object") continue;
    const node = n as Record<string, unknown>;
    if (node.type === "text") {
      let t = String(node.text ?? "");
      const marks = Array.isArray(node.marks) ? node.marks : [];
      for (const m of marks) {
        if (!m || typeof m !== "object") continue;
        const mt = (m as Record<string, unknown>).type;
        if (mt === "bold") t = `**${t}**`;
        else if (mt === "italic") t = `*${t}*`;
        else if (mt === "code") t = `\`${t}\``;
      }
      out += t;
    } else if (node.type === "hardBreak") {
      out += "\n";
    } else if (node.type === "mathInline") {
      const latex = String(((node as Record<string, unknown>).attrs as Record<string, unknown> | undefined)?.latex ?? "");
      out += `$${latex}$`;
    } else if (node.type === "citation") {
      out += String((node.attrs as Record<string, unknown> | undefined)?.renderedText ?? "（引用）");
    }
  }
  return out;
}

function blockToMd(node: unknown, depth = 0): string {
  if (!node || typeof node !== "object") return "";
  const n = node as Record<string, unknown>;
  const t = n.type;

  if (t === "paragraph") {
    const pid = String((n.attrs as Record<string, unknown>)?.paragraphId ?? "").trim();
    const body = inlineToMd(n.content as unknown[]);
    return pid ? `<!-- pid:${pid} -->\n${body}` : body;
  }
  if (t === "heading") {
    const level = Number((n.attrs as Record<string, unknown>)?.level ?? 1);
    const hashes = "#".repeat(Math.max(1, Math.min(6, level)));
    return `${hashes} ${inlineToMd(n.content as unknown[])}`;
  }
  if (t === "blockquote") {
    const inner = blocksToMd(n.content as unknown[], depth);
    return inner
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
  }
  if (t === "codeBlock") {
    const lang = String((n.attrs as Record<string, unknown>)?.language ?? "").trim();
    const body = inlineToMd(n.content as unknown[]);
    return lang ? `\`\`\`${lang}\n${body}\n\`\`\`` : `\`\`\`\n${body}\n\`\`\``;
  }
  if (t === "mathBlock") {
    const attrs = n.attrs as Record<string, unknown>;
    const latex = String(attrs?.latex ?? "");
    const numbered = Boolean(attrs?.numbered);
    const eqNum = String(attrs?.equationNumber ?? "").trim();
    const label = String(attrs?.label ?? "").trim();
    let body = `$$\n${latex}\n$$`;
    if (numbered && eqNum) {
      body += `\n<!-- eq-number:${eqNum} -->`;
    }
    if (label) {
      body += `\n<!-- eq-label:${label} -->`;
    }
    return body;
  }
  if (t === "bulletList" || t === "orderedList") {
    const items = (n.content as unknown[]) ?? [];
    const lines: string[] = [];
    let idx = 1;
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const it = item as Record<string, unknown>;
      if (it.type !== "listItem") continue;
      const itemLines = listItemBodyToMd(it.content as unknown[], depth + 1);
      if (itemLines.length === 0) continue;
      for (const line of itemLines) {
        if (t === "orderedList") {
          lines.push(`${idx}. ${line}`);
          idx += 1;
        } else {
          lines.push(`- ${line}`);
        }
      }
    }
    return lines.join("\n");
  }
  if (t === "table") {
    const rows = ((n.content as unknown[]) ?? []).filter(
      (r) => r && typeof r === "object" && (r as Record<string, unknown>).type === "tableRow",
    ) as Record<string, unknown>[];
    const mdRows: string[] = [];
    for (let ri = 0; ri < rows.length; ri += 1) {
      const cells = ((rows[ri].content as unknown[]) ?? []).filter(
        (c) =>
          c &&
          typeof c === "object" &&
          ["tableCell", "tableHeader"].includes(String((c as Record<string, unknown>).type)),
      ) as Record<string, unknown>[];
      const texts = cells.map((cell) => {
        const paras = (cell.content as unknown[]) ?? [];
        return paras
          .map((p) => {
            if (!p || typeof p !== "object") return "";
            const para = p as Record<string, unknown>;
            if (para.type === "paragraph") {
              return inlineToMd(para.content as unknown[]);
            }
            return blockToMd(p, depth);
          })
          .filter(Boolean)
          .join(" ")
          .trim();
      });
      mdRows.push(`| ${texts.join(" | ")} |`);
      if (ri === 0) {
        mdRows.push(`| ${texts.map(() => "---").join(" | ")} |`);
      }
    }
    return mdRows.join("\n");
  }
  if (t === "figureBlock") {
    const attrs = (n.attrs as Record<string, unknown>) ?? {};
    return figureBlockToAnnotation(attrs);
  }
  if (t === "mathInline") {
    const latex = String((n.attrs as Record<string, unknown>)?.latex ?? "");
    return `$${latex}$`;
  }
  return "";
}

/** 列表项内段落 pid 与正文同一行，避免导出成 `- <!-- pid -->\n- \n` 损坏对。 */
function listItemBodyToMd(nodes: unknown[] | undefined, depth: number): string[] {
  if (!Array.isArray(nodes)) return [];
  const lines: string[] = [];
  for (const node of nodes) {
    if (!node || typeof node !== "object") continue;
    const n = node as Record<string, unknown>;
    if (n.type === "paragraph") {
      const pid = String((n.attrs as Record<string, unknown>)?.paragraphId ?? "").trim();
      const body = inlineToMd(n.content as unknown[]);
      if (!body.trim()) continue;
      lines.push(pid ? `<!-- pid:${pid} -->${body}` : body);
      continue;
    }
    const block = blockToMd(n, depth);
    if (block.trim()) lines.push(...block.split("\n").filter(Boolean));
  }
  return lines;
}

function blocksToMd(nodes: unknown[] | undefined, depth = 0): string {
  if (!Array.isArray(nodes)) return "";
  const chunks: string[] = [];
  for (const node of nodes) {
    const s = blockToMd(node, depth);
    if (s) chunks.push(s);
  }
  return chunks.join("\n\n");
}

/** 从 TipTap 文档还原可持久化的 Markdown（保留 DIAGRAM、表格、公式等） */
export function tiptapDocToMarkdown(doc: Record<string, unknown> | null | undefined): string {
  if (!doc || doc.type !== "doc") return "";
  return blocksToMd(doc.content as unknown[]).trim();
}
