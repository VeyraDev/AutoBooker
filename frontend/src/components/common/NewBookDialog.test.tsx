// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import NewBookDialog from "@/components/common/NewBookDialog";

const api = vi.hoisted(() => ({
  createBook: vi.fn(),
  startAutoGenerate: vi.fn(),
  createOptimizationProject: vi.fn(),
}));

vi.mock("@/api/books", () => ({
  createBook: api.createBook,
}));

vi.mock("@/api/bookJobs", () => ({
  startAutoGenerate: api.startAutoGenerate,
}));

vi.mock("@/api/optimization", () => ({
  createOptimizationProject: api.createOptimizationProject,
}));

function LocationProbe() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter
      initialEntries={["/app/home"]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <QueryClientProvider client={queryClient}>
        <NewBookDialog open onClose={() => undefined} />
        <LocationProbe />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NewBookDialog one-click workflow", () => {
  it("creates the book job atomically and opens the progress page", async () => {
    api.startAutoGenerate.mockResolvedValue({
      id: "job-1",
      book_id: "book-1",
      status: "pending",
      current_step: null,
      progress_pct: 0,
      error_message: null,
    });

    renderDialog();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "一键成书" }));
    await user.type(
      screen.getByPlaceholderText("例如：人工智能如何改变商业决策"),
      "功能测试书稿",
    );
    await user.click(screen.getByRole("button", { name: "开始一键成书" }));

    await waitFor(() => {
      expect(api.startAutoGenerate).toHaveBeenCalledWith({
        title: "功能测试书稿",
        book_type: "nonfiction",
        style_type: "popular_science",
      });
    });
    expect(api.createBook).not.toHaveBeenCalled();
    expect(screen.getByTestId("location").textContent).toBe(
      "/app/books/book-1/auto-progress",
    );
  });
});
