// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

vi.mock("@/features/assistant/api/assistantApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/assistant/api/assistantApi")>();
  return {
    ...actual,
    getOutlineReadiness: vi.fn().mockResolvedValue({ missing: [], ready: true, outline_route: null }),
    sendTurn: vi.fn(),
  };
});

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
    quickFill: vi.fn(),
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
    lastQuickFillOpId: null,
    lastSettingOrigins: {},
    lastConfirmedRequirements: [],
    lastOutlineRoute: null,
  }),
}));

afterEach(() => cleanup());

describe("ProjectAssistantPage", () => {
  it("renders assistant layout with project brief panel", async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <ProjectAssistantPage bookId="book-1" onExit={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("资料库")).toBeTruthy();
    expect(screen.getByRole("button", { name: "返回书架" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "快速补齐" })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("书稿设定")).toBeTruthy();
      expect(screen.getByRole("button", { name: "生成大纲" })).toBeTruthy();
    });
  });
});
