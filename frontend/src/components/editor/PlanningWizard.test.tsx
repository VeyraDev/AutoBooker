// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import PlanningWizard from "@/components/editor/PlanningWizard";
import type { Book } from "@/types/book";

const setup = vi.hoisted(() => ({
  saveMeta: vi.fn(),
}));

vi.mock("@/components/editor/SetupView", async () => {
  const React = await import("react");
  return {
    default: ({
      onRegisterActions,
    }: {
      onRegisterActions?: (actions: { saveMeta: typeof setup.saveMeta }) => void;
    }) => {
      React.useEffect(() => {
        onRegisterActions?.({ saveMeta: setup.saveMeta });
      }, [onRegisterActions]);
      return <div>书稿设定表单</div>;
    },
  };
});

vi.mock("@/components/editor/OutlineReviewPanel", () => ({
  default: ({ leftAside }: { leftAside?: React.ReactNode }) => (
    <div>
      <div>大纲预览</div>
      {leftAside}
    </div>
  ),
}));

const initialBook: Book = {
  id: "book-1",
  user_id: "user-1",
  title: "测试书稿",
  workflow_mode: "from_scratch",
  book_type: "nonfiction",
  discipline: null,
  citation_style: "apa",
  target_words: 80000,
  status: "setup",
  style_type: "popular_science",
  topic_tags: null,
  topic_brief: null,
  target_audience: null,
  created_at: "2026-07-03T00:00:00Z",
  updated_at: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PlanningWizard outline generation", () => {
  it("shows immediate feedback and generates with the saved settings", async () => {
    let resolveSave!: (book: Book) => void;
    setup.saveMeta.mockReturnValue(
      new Promise<Book>((resolve) => {
        resolveSave = resolve;
      }),
    );
    const onGenerateOutline = vi.fn().mockResolvedValue(true);

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <PlanningWizard
            book={initialBook}
            bookId={initialBook.id}
            outline={undefined}
            outlineRequestPending={false}
            outlineGeneratingUi={false}
            onPatchBook={() => undefined}
            onGenerateOutline={onGenerateOutline}
            onStartWriting={vi.fn()}
            onOutlinePatched={() => undefined}
            onReorder={() => undefined}
            onDeleteChapter={() => undefined}
            dragDisabled
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "生成大纲" }));
    expect(
      (screen.getByRole("button", { name: "正在保存设定…" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    await act(async () => {
      resolveSave({
        ...initialBook,
        target_audience: "保存后的目标读者",
        topic_brief: "保存后的主题说明",
      });
    });

    await waitFor(() => {
      expect(onGenerateOutline).toHaveBeenCalledWith({
        topic_override: null,
        target_audience: "保存后的目标读者",
        topic_brief: "保存后的主题说明",
      });
    });
  });

  it("returns to startup assistant via onBackToBookSettings", async () => {
    const onBackToBookSettings = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <PlanningWizard
            book={{ ...initialBook, status: "outline_ready" }}
            bookId={initialBook.id}
            outline={{
              book_id: initialBook.id,
              chapters: [
                {
                  id: "c1",
                  chapter_index: 1,
                  title: "第一章",
                  summary: "",
                  target_words: 5000,
                  status: "pending",
                },
              ],
            } as never}
            outlineRequestPending={false}
            outlineGeneratingUi={false}
            onPatchBook={() => undefined}
            onGenerateOutline={vi.fn()}
            onStartWriting={vi.fn()}
            onOutlinePatched={() => undefined}
            onReorder={() => undefined}
            onDeleteChapter={() => undefined}
            dragDisabled
            onBackToBookSettings={onBackToBookSettings}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "← 返回书稿设定" }));
    expect(onBackToBookSettings).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("书稿设定表单")).toBeNull();
  });
});
