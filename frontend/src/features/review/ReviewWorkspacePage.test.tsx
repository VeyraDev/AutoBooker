// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import ReviewWorkspacePage from "@/features/review/ReviewWorkspacePage";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  client: api,
}));

vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/app/books/book-1/review"]}>
        <Routes>
          <Route path="/app/books/:bookId/review" element={<ReviewWorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReviewWorkspacePage", () => {
  it("renders three columns and must_fix count", async () => {
    api.get.mockImplementation((url: string) => {
      if (url.endsWith("/books/book-1")) {
        return Promise.resolve({ data: { id: "book-1", title: "测试书", status: "review_ready" } });
      }
      if (url.endsWith("/outline")) {
        return Promise.resolve({ data: { chapters: [{ index: 1, title: "第一章" }] } });
      }
      if (url.endsWith("/review-workspace/summary")) {
        return Promise.resolve({
          data: {
            book_id: "book-1",
            must_fix_count: 2,
            suggest_count: 1,
            observe_count: 3,
            needs_verification_count: 1,
            open_count: 6,
            run_status: "completed",
            by_chapter: { "1": 2 },
            latest_task: {
              id: "task-1",
              book_id: "book-1",
              scope: "book",
              chapter_indexes: null,
              goal: "default",
              custom_prompt: null,
              adopted_standards: { public_rules: true },
              exclusions: [],
              status: "completed",
              summary_text: "本次审校任务单\n\n审校范围：全书",
              run_id: "run-1",
              created_at: null,
            },
          },
        });
      }
      if (url.endsWith("/review-workspace/findings")) {
        return Promise.resolve({
          data: [
            {
              id: "f1",
              source: "chapter",
              chapter_index: 1,
              chapter_title: "第一章",
              tier: "must_fix",
              status: "open",
              title: "表达生硬",
              detail: "句子模式化",
              quote: "由此可见",
              suggestion: "改为具体描述",
              basis_refs: ["用户要求（避免）：不要营销腔"],
              category: "style",
              track: null,
              detector: "ai_detect",
              dimension: "ai_signature",
              issue_type: "generic_phrasing",
              product_dimension: "argument_quality",
              impact_scope: "sentence",
              locatable: true,
              task_id: null,
              validation_passed: true,
              filter_reason: null,
              why_it_matters: "影响读者判断",
              verification_status: null,
              action_options: [],
              fix_capability: "preview_apply",
              prefer_evidence_binding: false,
            },
            {
              id: "f2",
              source: "chapter",
              chapter_index: 1,
              chapter_title: "第一章",
              tier: "needs_verification",
              status: "open",
              title: "数据缺少来源",
              detail: "具体比例缺少可核验来源",
              quote: "90% 的团队...",
              suggestion: null,
              basis_refs: [],
              category: "reference_authenticity",
              track: null,
              detector: "reference_authenticity_reviewer",
              dimension: "citation_sources",
              issue_type: "missing_citation",
              product_dimension: "evidence_citation",
              impact_scope: "sentence",
              locatable: true,
              task_id: null,
              validation_passed: true,
              filter_reason: null,
              why_it_matters: "影响事实可信度",
              verification_status: "needs_verification",
              action_options: [],
              fix_capability: "choice_then_apply",
              prefer_evidence_binding: true,
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });

    renderPage();

    expect(await screen.findByText("审校工作台")).toBeTruthy();
    expect(await screen.findByText("专项审校")).toBeTruthy();
    expect(await screen.findByText("问题列表")).toBeTruthy();
    expect(await screen.findByText("选择左侧问题查看详情与依据")).toBeTruthy();
    expect(await screen.findByText("必改 (1)")).toBeTruthy();
    expect(await screen.findByText("待核验 (1)")).toBeTruthy();
    expect(screen.getByText("2", { selector: ".text-red-700" })).toBeTruthy();
    expect(await screen.findByText("表达生硬")).toBeTruthy();
    expect(await screen.findByText("可预览应用")).toBeTruthy();

    expect(await screen.findByRole("button", { name: "batch-preview-findings" })).toBeTruthy();

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/books/book-1/review-workspace/summary");
    });
  });
});
