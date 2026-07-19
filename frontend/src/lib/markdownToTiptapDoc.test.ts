import { describe, expect, it } from "vitest";

import { buildTiptapDocWithFigures } from "@/lib/buildTiptapDocWithFigures";

function collectTypes(node: unknown, out: string[] = []): string[] {
  if (!node || typeof node !== "object") return out;
  const current = node as Record<string, unknown>;
  if (typeof current.type === "string") out.push(current.type);
  if (Array.isArray(current.content)) {
    for (const child of current.content) collectTypes(child, out);
  }
  return out;
}

function hasBoldMark(node: unknown): boolean {
  if (!node || typeof node !== "object") return false;
  const current = node as Record<string, unknown>;
  if (
    Array.isArray(current.marks) &&
    current.marks.some(
      (mark) =>
        mark && typeof mark === "object" && (mark as Record<string, unknown>).type === "bold",
    )
  ) {
    return true;
  }
  return Array.isArray(current.content) && current.content.some(hasBoldMark);
}

describe("complete chapter Markdown conversion", () => {
  it("preserves headings, bold, tables, code, math and generated figures together", () => {
    const doc = buildTiptapDocWithFigures(
      `## 第一节 完整渲染

这是**加粗文字**，并包含公式 $E=mc^2$。

| 维度 | 结论 |
| --- | --- |
| 速度 | 快 |

\`\`\`mermaid
flowchart LR
  A --> B
\`\`\`

[DIAGRAM: 展示完整处理流程]

图1-1：处理流程`,
      [],
    );

    const types = collectTypes(doc);
    expect(types).toContain("heading");
    expect(types).toContain("table");
    expect(types).toContain("codeBlock");
    expect(types).toContain("mathInline");
    expect(types).toContain("figureBlock");
    expect(hasBoldMark(doc)).toBe(true);
  });
});
