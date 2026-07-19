import { describe, expect, it } from "vitest";

import {
  CITATION_MANAGEMENT_VIEWS,
  citationSequenceLabel,
} from "@/lib/citationManagement";

describe("citation management presentation", () => {
  it("exposes only literature search and citation management", () => {
    expect(CITATION_MANAGEMENT_VIEWS).toEqual([
      ["search", "文献搜索"],
      ["manage", "引用管理"],
    ]);
  });

  it("shows formal sequence numbers only for used GB/T references", () => {
    expect(citationSequenceLabel("gb_t7714", 3)).toBe("[3] ");
    expect(citationSequenceLabel("gb_t7714", null)).toBe("");
    expect(citationSequenceLabel("apa", 3)).toBe("");
    expect(citationSequenceLabel("mla", 3)).toBe("");
    expect(citationSequenceLabel("chicago", 3)).toBe("");
  });
});
