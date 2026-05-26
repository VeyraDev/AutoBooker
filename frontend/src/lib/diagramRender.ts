import { instance as vizInstance, type Viz } from "@viz-js/viz";

import type { DiagramEngine } from "@/lib/diagramTypes";
import { normalizePlantumlCode } from "@/lib/diagramUtils";

let vizReady: Viz | null = null;

async function getViz(): Promise<Viz> {
  if (!vizReady) vizReady = await vizInstance();
  return vizReady;
}

/** 保持 SVG 原始宽高比，居中显示、防裁切 */
export function patchDiagramSvgRoot(root: HTMLElement) {
  root.querySelectorAll("svg").forEach((svg) => {
    svg.style.display = "block";
    svg.style.width = "auto";
    svg.style.height = "auto";
    svg.style.maxWidth = "100%";
    svg.style.marginLeft = "auto";
    svg.style.marginRight = "auto";
    svg.style.overflow = "visible";
    svg.style.verticalAlign = "top";
  });
  root.querySelectorAll("foreignObject").forEach((fo) => {
    (fo as SVGForeignObjectElement).style.overflow = "visible";
  });
}

export async function renderGraphvizInto(container: HTMLElement, code: string): Promise<void> {
  const trimmed = code.trim();
  if (!trimmed) {
    container.innerHTML = "";
    return;
  }
  const viz = await getViz();
  const svgEl = viz.renderSVGElement(trimmed, { engine: "dot" });
  container.innerHTML = "";
  container.appendChild(svgEl);
  patchDiagramSvgRoot(container);
}

export async function renderPlantumlInto(container: HTMLElement, code: string): Promise<void> {
  const trimmed = code.trim();
  if (!trimmed) {
    container.innerHTML = "";
    return;
  }
  const puml = normalizePlantumlCode(trimmed);
  const res = await fetch("https://kroki.io/plantuml/svg", {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: puml,
  });
  if (!res.ok) {
    throw new Error(`PlantUML 渲染失败 (${res.status})`);
  }
  const svg = await res.text();
  if (/Syntax Error|cannot parse/i.test(svg)) {
    throw new Error("PlantUML 语法错误");
  }
  container.innerHTML = svg;
  patchDiagramSvgRoot(container);
}

export async function renderDiagramInto(
  container: HTMLElement,
  engine: DiagramEngine,
  code: string,
): Promise<void> {
  if (engine === "plantuml") {
    await renderPlantumlInto(container, code);
  } else {
    await renderGraphvizInto(container, code);
  }
}
