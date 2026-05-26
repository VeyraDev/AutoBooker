/** 流程图/概念图 → Graphviz；时序图/架构图 → PlantUML */
export type DiagramEngine = "graphviz" | "plantuml";

export type ExtractedDiagram = {
  engine: DiagramEngine;
  code: string;
};
