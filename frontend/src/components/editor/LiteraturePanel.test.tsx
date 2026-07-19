// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LiteraturePanel from "@/components/editor/LiteraturePanel";
import type { CitationRecord } from "@/types/literature";

const citationApi = vi.hoisted(() => ({
  deleteCitationOccurrence: vi.fn(),
  getCitationVerificationJob: vi.fn(),
  listCitationOccurrences: vi.fn(),
  listCitations: vi.fn(),
  listCitationVerificationJobs: vi.fn(),
  refreshCitationVerification: vi.fn(),
  startCitationVerificationJob: vi.fn(),
  weaveCitation: vi.fn(),
}));

const sourceSearchApi = vi.hoisted(() => ({
  addSourceSearchResults: vi.fn(),
  listSourceSearchCapabilities: vi.fn(),
  searchSources: vi.fn(),
}));

vi.mock("@/api/citations", () => citationApi);

vi.mock("@/api/literature", () => ({
  refineLiteratureQuery: vi.fn(),
}));

vi.mock("@/api/sourceSearch", () => sourceSearchApi);

vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const baseCitation: CitationRecord = {
  id: "citation-1",
  book_id: "book-1",
  doi: "",
  title: "对强人工智能及其理论预设的考察",
  authors: ["王佳", "朱敏"],
  year: 2010,
  journal: "心智与计算",
  format_cache: null,
  source: "uploaded_file",
  source_file_id: null,
  raw_text: null,
  quotable_snippet: null,
  abstract_preview: null,
  url: null,
  document_type: "journal_article",
  publisher: null,
  volume: "4",
  issue: "1",
  pages: "1-7",
  metadata_status: "complete",
  external_source: null,
  list_index: 1,
  verification_status: "needs_verification",
  verification_result: null,
  last_verified_at: null,
  formatted: null,
  created_at: "2026-07-19T00:00:00Z",
};

function renderPanel() {
  return render(
    <LiteraturePanel
      bookId="book-1"
      citationStyle="gb_t7714"
      mode="editor"
    />,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  citationApi.listCitations.mockResolvedValue([baseCitation]);
  citationApi.listCitationOccurrences.mockResolvedValue([]);
  citationApi.listCitationVerificationJobs.mockResolvedValue([]);
  citationApi.refreshCitationVerification.mockResolvedValue({
    ...baseCitation,
    verification_status: "verified",
    last_verified_at: "2026-07-19T10:30:00Z",
  });
  citationApi.startCitationVerificationJob.mockResolvedValue({
    id: "job-1",
    book_id: "book-1",
    status: "completed",
    requested_citation_ids: ["citation-1"],
    total_count: 1,
    processed_count: 1,
    succeeded_count: 1,
    failed_count: 0,
    progress_pct: 100,
    result_json: { status_counts: { verified: 1 } },
    error_message: null,
    created_at: "2026-07-19T11:00:00Z",
    finished_at: "2026-07-19T11:00:01Z",
  });
  sourceSearchApi.listSourceSearchCapabilities.mockResolvedValue([
    { id: "paper", label: "论文", available: true, connectors: ["openalex"] },
    { id: "news", label: "新闻/访谈", available: true, connectors: ["tavily"] },
  ]);
  sourceSearchApi.searchSources.mockResolvedValue({
    query: "人物访谈",
    papers: [],
    github: [],
    wiki: [],
    official_docs: [],
    refined_queries: ["人物访谈 新闻 采访 专访 报道"],
    items: [
      {
        id: "news-1",
        title: "一次公开访谈",
        authors: [],
        url: "https://example.com/interview",
        source_type: "news",
        provider: "tavily",
        snippet: "访谈摘要",
        citeability: false,
        metadata_missing: ["责任者", "日期"],
      },
    ],
    facets: [{ id: "news", label: "新闻/访谈", count: 1 }],
    execution: {
      requested_source_types: ["news"],
      attempted_connectors: ["tavily:news"],
      successful_connectors: ["tavily:news"],
      failed_connectors: {},
      unavailable_source_types: [],
      degraded: false,
      duration_ms: 320,
      result_counts: { news: 1 },
    },
  });
  sourceSearchApi.addSourceSearchResults.mockResolvedValue({
    target: "source_library",
    added_count: 1,
    sources: [],
    citations: [],
    rejected: [],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LiteraturePanel citation verification", () => {
  it("runs a new backend search when the source group changes", async () => {
    renderPanel();
    const input = await screen.findByPlaceholderText("人物、事件、图书、政策、报告或主题…");
    await userEvent.type(input, "人物访谈");
    await userEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => expect(sourceSearchApi.searchSources).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("一次公开访谈")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "新闻/访谈 (1)" }));
    await waitFor(() => expect(sourceSearchApi.searchSources).toHaveBeenCalledTimes(2));
    expect(sourceSearchApi.searchSources.mock.calls[1][1].sourceTypes).toEqual(["news"]);
    await userEvent.click(await screen.findByLabelText("选择：一次公开访谈"));
    expect(screen.getByRole("button", { name: "加入文献库" }).hasAttribute("disabled")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "加入资料库" }));
    await waitFor(() => {
      expect(sourceSearchApi.addSourceSearchResults).toHaveBeenCalledWith(
        "book-1",
        "source_library",
        expect.arrayContaining([expect.objectContaining({ title: "一次公开访谈" })]),
      );
    });
  });

  it("renders verification status and refreshes a single citation", async () => {
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "引用管理" }));

    expect(await screen.findByText(/对强人工智能及其理论预设的考察/)).toBeTruthy();
    expect(screen.getByText("待核验")).toBeTruthy();
    expect(screen.getByText("缺少强外部匹配或关键元数据")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "刷新核验" }));

    await waitFor(() => {
      expect(citationApi.refreshCitationVerification).toHaveBeenCalledWith("book-1", "citation-1");
    });
    expect(await screen.findByText("已核验")).toBeTruthy();
  });

  it("refreshes selected citations in batch", async () => {
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "引用管理" }));
    await userEvent.click(await screen.findByLabelText("选择：对强人工智能及其理论预设的考察"));
    await userEvent.click(screen.getByRole("button", { name: "刷新已选核验" }));

    await waitFor(() => {
      expect(citationApi.startCitationVerificationJob).toHaveBeenCalledWith("book-1", ["citation-1"], false);
    });
    expect(citationApi.listCitations.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("starts a retry job for unreachable citations", async () => {
    citationApi.listCitations.mockResolvedValue([
      {
        ...baseCitation,
        verification_status: "unreachable",
      },
    ]);
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "引用管理" }));
    await userEvent.click(await screen.findByRole("button", { name: "重试失败核验" }));

    await waitFor(() => {
      expect(citationApi.startCitationVerificationJob).toHaveBeenCalledWith("book-1", undefined, true);
    });
  });

  it("asks for confirmation before refreshing a large unselected batch", async () => {
    const many = Array.from({ length: 51 }, (_, index) => ({
      ...baseCitation,
      id: `citation-${index + 1}`,
      title: `文献 ${index + 1}`,
    }));
    citationApi.listCitations.mockResolvedValue(many);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "引用管理" }));
    await userEvent.click(await screen.findByRole("button", { name: "刷新全部核验" }));

    expect(confirm).toHaveBeenCalled();
    expect(citationApi.startCitationVerificationJob).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});
