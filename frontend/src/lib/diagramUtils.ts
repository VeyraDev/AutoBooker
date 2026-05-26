import type { DiagramEngine, ExtractedDiagram } from "@/lib/diagramTypes";

const GRAPHVIZ_FENCE = /```(?:dot|graphviz|digraph)\s*([\s\S]*?)```/i;
const PLANTUML_FENCE = /```(?:plantuml|puml)\s*([\s\S]*?)```/i;

/** 根据源码推断渲染引擎 */
export function detectDiagramEngine(code: string): DiagramEngine {
  const s = code.trim();
  if (/^@start/i.test(s)) return "plantuml";
  if (/^(digraph|graph|strict\s+(digraph|graph))\b/im.test(s)) return "graphviz";
  if (/^(sequence|participant|actor|skinparam|component|package|node|cloud|database|rectangle)\b/im.test(s)) {
    return "plantuml";
  }
  return "graphviz";
}

/** 从 AI 输出或 Markdown 中提取图表源码 */
export function extractDiagramCode(raw: string): ExtractedDiagram | null {
  const s = raw.trim();
  if (!s) return null;

  const gvFence = s.match(GRAPHVIZ_FENCE);
  if (gvFence) return { engine: "graphviz", code: gvFence[1].trim() };

  const pumlFence = s.match(PLANTUML_FENCE);
  if (pumlFence) return { engine: "plantuml", code: pumlFence[1].trim() };

  if (/^@start/i.test(s)) return { engine: "plantuml", code: s };
  if (/^(digraph|graph|strict\s+(digraph|graph))\b/im.test(s)) {
    return { engine: "graphviz", code: s };
  }

  return null;
}

/** 将 PlantUML 源码包裹为完整文档 */
export function normalizePlantumlCode(code: string): string {
  const trimmed = code.trim();
  if (!trimmed) return trimmed;
  if (/^@start/i.test(trimmed)) return trimmed;
  return `@startuml\n${trimmed}\n@enduml`;
}