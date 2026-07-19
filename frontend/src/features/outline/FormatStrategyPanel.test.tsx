// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import FormatStrategyPanel from "@/features/outline/FormatStrategyPanel";

vi.mock("@/features/outline/formatStrategyApi", () => ({
  getFormatStrategy: vi.fn().mockResolvedValue({
    id: "fs-1",
    book_id: "book-1",
    version: 1,
    status: "draft",
    book_level_columns: [{ column_name: "操作步骤", purpose: "指导读者操作" }],
    conditional_columns: [{ column_name: "故障排查", purpose: "排错", appearance_condition: "安装章" }],
    forbidden_patterns: ["每章强制相同顺序"],
    chapter_suggestions: {
      "1": [{ column_name: "概念梳理", purpose: "理解概念" }],
      "2": [{ column_name: "故障排查", purpose: "排错" }],
    },
  }),
  generateFormatStrategy: vi.fn(),
  confirmFormatStrategy: vi.fn(),
}));

afterEach(() => cleanup());

describe("FormatStrategyPanel", () => {
  it("renders format strategy sections and confirm button", async () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <FormatStrategyPanel
          bookId="book-1"
          chapters={[
            { id: "c1", index: 1, title: "引言", summary: "", key_points: [], estimated_words: 3000, sections: [], word_count: 0, status: "pending" },
            { id: "c2", index: 2, title: "安装", summary: "", key_points: [], estimated_words: 3000, sections: [], word_count: 0, status: "pending" },
          ]}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("体例与栏目")).toBeTruthy();
    expect(screen.getByText("书级固定栏目")).toBeTruthy();
    expect(screen.getByRole("button", { name: "确认栏目策略" })).toBeTruthy();
    expect(screen.getByText(/第2章 安装/)).toBeTruthy();
  });
});
