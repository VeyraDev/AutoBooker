import { describe, expect, it } from "vitest";

import { buildSeedFromToolResults, panelHintToTab } from "@/features/assistant/toolDispatch";

describe("toolDispatch", () => {
  it("maps literature hint to tab", () => {
    expect(panelHintToTab("literature")).toBe("literature");
    expect(panelHintToTab("review")).toBe("review");
    expect(panelHintToTab("memory")).toBe("memory");
  });

  it("builds literature seed from tool results", () => {
    const seed = buildSeedFromToolResults([
      {
        name: "search_literature",
        ok: true,
        panel_hint: "literature",
        data: {
          query: "transformer",
          papers: [{ title: "Attention", authors: ["Vaswani"], year: 2017 }],
          github: [],
          wiki: [],
          official_docs: [],
          items: [],
          refined_queries: ["transformer attention"],
        },
      },
    ]);
    expect(seed.literatureQuery).toBe("transformer");
    expect(seed.literatureResult?.papers).toHaveLength(1);
  });
});
