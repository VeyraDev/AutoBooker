// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
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
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReviewFindingDetail", () => {
  it("shows basis refs and recheck button for pending recheck", async () => {
    api.get.mockResolvedValue({ data: [] });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ReviewFindingDetail bookId="book-1" finding={finding} onUpdated={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("依据来源")).toBeTruthy();
    expect(screen.getByText(/不要营销腔/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "复查本条" })).toBeTruthy();
  });
});
