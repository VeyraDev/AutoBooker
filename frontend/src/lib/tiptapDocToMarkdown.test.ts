import { describe, expect, it } from "vitest";

import { tiptapDocToMarkdown } from "@/lib/tiptapDocToMarkdown";

describe("structured citation serialization", () => {
  it("renders citation nodes with their current formatted text", () => {
    const doc = {
      type: "doc",
      content: [
        {
          type: "paragraph",
          content: [
            { type: "text", text: "研究表明" },
            {
              type: "citation",
              attrs: {
                nodeId: "node-1",
                citationId: "citation-1",
                evidenceId: "evidence-1",
                citeMode: "parenthetical",
                locator: "p. 12",
                prefix: "",
                suffix: "",
                renderedText: "(Lovelace, 1843, p. 12)",
              },
            },
            { type: "text", text: "。" },
          ],
        },
      ],
    };

    expect(tiptapDocToMarkdown(doc)).toContain(
      "研究表明(Lovelace, 1843, p. 12)。",
    );
  });
});
