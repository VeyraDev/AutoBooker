import { describe, expect, it } from "vitest";

import { mergeLiteratureSelection } from "@/lib/literatureSelection";

describe("mergeLiteratureSelection", () => {
  it("keeps selections from earlier source tabs when selecting the current page", () => {
    const papers = new Set(["papers:one", "papers:two"]);

    expect([...mergeLiteratureSelection(papers, ["github:one", "github:two"])]).toEqual([
      "papers:one",
      "papers:two",
      "github:one",
      "github:two",
    ]);
  });
});
