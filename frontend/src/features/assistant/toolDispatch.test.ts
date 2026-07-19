import { describe, expect, it } from "vitest";

import { buildSeedFromToolResults, panelHintToTab } from "@/features/assistant/toolDispatch";

describe("toolDispatch", () => {
  it("maps literature hint to tab", () => {
    expect(panelHintToTab("literature")).toBe("literature");
    expect(panelHintToTab("review")).toBeNull();
    expect(panelHintToTab("memory")).toBeNull();
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

  it("unwraps search_references nested result", () => {
    const seed = buildSeedFromToolResults([
      {
        name: "search_references",
        ok: true,
        panel_hint: "literature",
        data: {
          raw_query: "健康城市",
          queries: ["healthy city", "health impact assessment"],
          result: {
            query: "健康城市",
            papers: [{ title: "HIA", authors: ["A"], year: 2020 }],
            github: [],
            wiki: [{ title: "Walkability", authors: [], year: null }],
            official_docs: [],
            items: [],
            refined_queries: ["healthy city"],
          },
        },
      },
    ]);
    expect(seed.literatureQuery).toBe("健康城市");
    expect(seed.literatureResult?.papers).toHaveLength(1);
    expect(seed.literatureResult?.wiki).toHaveLength(1);
  });
});
