// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReviewFindingDetail from "@/features/review/ReviewFindingDetail";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));

vi.mock("@/api/client", () => ({ client: api }));
vi.mock("@/api/review", () => ({
  confirmReviewApplication: vi.fn(),
  undoReviewApplication: vi.fn(),
}));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));

const finding = {
  id: "f1",
  source: "chapter" as const,
  chapter_index: 1,
  chapter_title: "第一章",
  tier: "must_fix" as const,
  status: "applied_pending_recheck",
  title: "表达问题",
  detail: "句子模式化",
  quote: "由此可见",
  suggestion: "改为具体描述",
  basis_refs: ["用户要求（避免）：不要营销腔", "内置编辑标准：避免营销腔开场"],
  evidence_items: [
    {
      type: "title_benchmark",
      label: "标题样本基准",
      detail: "参考 data/document 中 20 个可识别标题，常见区间约 6-27 个中文字符，中位数约 16。",
      source: "data/document",
      examples: ["AI工程 大模型应用开发实战", "从零构建大语言模型"],
    },
  ],
  paragraph_id: null,
  paragraph_index: 2,
  char_start: 120,
  char_end: 128,
  category: "style",
  track: null,
  detector: "review_agent",
  dimension: "style",
  issue_type: "generic_phrasing",
  product_dimension: "language_credibility" as const,
  impact_scope: "sentence",
  locatable: true,
  task_id: null,
  validation_passed: true,
  filter_reason: null,
  why_it_matters: "影响读者信任",
  verification_status: null,
  action_options: [],
  fix_capability: "manual_only" as const,
  prefer_evidence_binding: false,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReviewFindingDetail", () => {
  it("shows basis refs and recheck button for pending recheck", async () => {
    api.get.mockResolvedValue({ data: [] });
    const jump = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ReviewFindingDetail bookId="book-1" finding={finding} onUpdated={vi.fn()} onJumpToSource={jump} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("依据来源")).toBeTruthy();
    expect(screen.getByText("定位")).toBeTruthy();
    expect(screen.getByText(/第 1 章/)).toBeTruthy();
    expect(screen.getByText(/段落 3/)).toBeTruthy();
    expect(screen.getByText(/不要营销腔/)).toBeTruthy();
    expect(screen.getByText("标题样本基准")).toBeTruthy();
    expect(screen.getByText(/6-27 个中文字符/)).toBeTruthy();
    expect(screen.getByText("AI工程 大模型应用开发实战")).toBeTruthy();
    expect(screen.getAllByText("需人工处理").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "复查本条" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "跳转到正文" }));
    expect(jump).toHaveBeenCalledWith(finding);
  });

  it("allows a chapter-scoped full-book finding to jump to its manuscript anchor", async () => {
    api.get.mockResolvedValue({ data: [] });
    const jump = vi.fn();
    const bookFinding = {
      ...finding,
      id: "book-finding-1",
      source: "book" as const,
      status: "open",
      paragraph_index: 4,
      char_start: 90,
      char_end: 100,
      locatable: true,
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ReviewFindingDetail bookId="book-1" finding={bookFinding} onUpdated={vi.fn()} onJumpToSource={jump} />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "跳转到正文" }));
    expect(jump).toHaveBeenCalledWith(bookFinding);
    expect(screen.getByText(/段落 5/)).toBeTruthy();
  });
});
