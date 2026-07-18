// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ProjectAssistantPage from "@/features/assistant/components/ProjectAssistantPage";

vi.mock("@/api/books", () => ({
  getBook: vi.fn().mockResolvedValue({ id: "book-1", title: "书稿1" }),
}));

vi.mock("@/api/outline", () => ({
  generateOutline: vi.fn().mockResolvedValue({ title: "书稿1", chapters: [], total_chapters: 0, estimated_words: 0 }),
}));

vi.mock("@/features/intake/api/intakeApi", () => ({
  useIntake: () => ({
    data: { intake: { raw_goal_text: "测试意图", status: "collecting" } },
    isLoading: false,
    refetch: vi.fn(),
  }),
  completeProjectStart: vi.fn(),
}));

vi.mock("@/features/assistant/hooks/useWritingBasis", () => ({
  useWritingBasis: () => ({
    data: {
      id: "basis-1",
      book_promise: "",
      reader_outcome: "",
      scope: "",
      depth: "",
      voice: "",
      must_avoid: [],
      must_keep: [],
    },
    isLoading: false,
  }),
}));

vi.mock("@/features/assistant/hooks/useAssistantConversation", () => ({
  useAssistantConversation: () => ({
    turns: [],
    turnsLoading: false,
    sources: [],
    sourcesLoading: false,
    sourcesError: null,
    refetchSources: vi.fn(),
    refreshSources: vi.fn(),
    prependSource: vi.fn(),
    removeSource: vi.fn(),
    sendMessage: vi.fn(),
    sending: false,
    streaming: false,
    streamingText: "",
    pendingTurn: null,
    sendError: null,
    pendingConfirmations: [],
    topicProposal: undefined,
    externalSearch: null,
    toolResults: [],
    turnTracesById: {},
  }),
}));

afterEach(() => cleanup());

describe("ProjectAssistantPage", () => {
  it("renders assistant layout with project brief panel", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <ProjectAssistantPage bookId="book-1" onExit={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("项目要点")).toBeTruthy();
    expect(screen.getByText("资料库")).toBeTruthy();
    expect(screen.getByRole("button", { name: "返回书架" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成大纲" })).toBeTruthy();
  });
});
