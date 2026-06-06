import type { FigureBlockAttrs } from "@/lib/tiptap/FigureBlock";
import { ANNOTATION_FULL_RE } from "@/lib/annotationPatterns";
import { enrichInlineBoldInDoc } from "@/lib/enrichInlineBold";

/** 将旧版 diagramBlock / mermaidBlock 迁移为 figureBlock 占位 */
export function migrateTiptapDoc(doc: Record<string, unknown>): Record<string, unknown> {
  if (doc.type !== "doc" || !Array.isArray(doc.content)) return doc;

  const migrated = {
    ...doc,
    content: (doc.content as unknown[]).map((node) => migrateNode(node)),
  };
  return enrichInlineBoldInDoc(migrated);
}

function diagramToFigure(attrs: Record<string, unknown>): Record<string, unknown> {
  const code = String(attrs.code ?? "");
  return {
    type: "figureBlock",
    attrs: {
      figureId: "",
      figureType: "flowchart",
      figureNumber: "",
      caption: code.slice(0, 200),
      status: "pending",
      fileUrl: "",
      svgUrl: "",
      rawAnnotation: code,
    } satisfies Partial<FigureBlockAttrs>,
  };
}

function migrateNode(node: unknown): unknown {
  if (!node || typeof node !== "object") return node;
  const n = node as Record<string, unknown>;
  if (n.type === "mermaidBlock" || n.type === "diagramBlock") {
    return diagramToFigure((n.attrs as Record<string, unknown>) ?? {});
  }
  if (Array.isArray(n.content)) {
    return { ...n, content: n.content.map((child) => migrateNode(child)) };
  }
  return n;
}

/** 将 figureBlock attrs 序列化为源码标注 */
export function figureBlockToAnnotation(attrs: Record<string, unknown>): string {
  const type = String(attrs.figureType ?? "figure");
  const raw = String(attrs.rawAnnotation ?? attrs.caption ?? "");
  if (type === "screenshot") return `[SCREENSHOT: ${raw}]`;
  if (type === "flowchart") return `[FLOWCHART: ${raw}]`;
  if (type === "chart") return `[CHART: ${raw}]`;
  return `[DIAGRAM: ${raw}]`;
}

/** 从 markdown 文本提取标注行（源码视图用） */
export function extractAnnotationsFromText(text: string): string[] {
  return text.match(ANNOTATION_FULL_RE) ?? [];
}
