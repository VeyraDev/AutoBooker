import { describe, expect, it } from "vitest";

import {
  sanitizeChapterMarkdown,
  sanitizeTiptapChapterDoc,
} from "@/lib/sanitizeChapterMarkdown";

describe("sanitizeChapterMarkdown", () => {
  it("removes model dividers, quote markers, and title brackets", () => {
    const input = [
      "## [理论转译]",
      "",
      "---",
      "",
      "> 第一段",
      "＞ 第二段",
      "【结构性矛盾】",
      "[1]",
      "[DIAGRAM: 结构图]",
    ].join("\n");

    const output = sanitizeChapterMarkdown(input);

    expect(output).toContain("## 理论转译");
    expect(output).toContain("第一段");
    expect(output).toContain("第二段");
    expect(output).toContain("结构性矛盾");
    expect(output).toContain("[1]");
    expect(output).toContain("[DIAGRAM: 结构图]");
    expect(output).not.toContain("---");
    expect(output).not.toContain(">");
    expect(output).not.toContain("＞");
  });

  it("flattens persisted blockquotes and drops horizontal rules", () => {
    const doc = {
      type: "doc",
      content: [
        { type: "horizontalRule" },
        {
          type: "blockquote",
          content: [
            { type: "paragraph", content: [{ type: "text", text: "> 正文" }] },
          ],
        },
      ],
    };

    expect(sanitizeTiptapChapterDoc(doc)).toEqual({
      type: "doc",
      content: [
        { type: "paragraph", content: [{ type: "text", text: "正文" }] },
      ],
    });
  });
});
