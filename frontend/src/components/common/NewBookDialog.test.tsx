// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import NewBookDialog from "@/components/common/NewBookDialog";

const api = vi.hoisted(() => ({
  createBook: vi.fn(),
  initIntake: vi.fn(),
  createOptimizationProject: vi.fn(),
}));

vi.mock("@/api/books", () => ({
  createBook: api.createBook,
}));

vi.mock("@/features/intake/api/intakeApi", () => ({
  initIntake: api.initIntake,
}));

vi.mock("@/api/optimization", () => ({
  createOptimizationProject: api.createOptimizationProject,
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
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
  it("creates an intake-backed book before one-click generation can start", async () => {
    api.createBook.mockResolvedValue({ id: "book-1" });
    api.initIntake.mockResolvedValue({ intake_id: "intake-1", status: "collecting" });

    renderDialog();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "我只有想法，想先确定方向" }));
    await user.click(screen.getByRole("button", { name: "一键成书" }));
    await user.type(
      screen.getByPlaceholderText("例如：人工智能如何改变商业决策"),
      "功能测试书稿",
    );
    await user.click(screen.getByRole("button", { name: "创建并确认输入" }));

    await waitFor(() => {
      expect(api.createBook).toHaveBeenCalledWith({
        title: "功能测试书稿",
        book_type: "nonfiction",
        target_words: expect.any(Number),
        style_type: "popular_science",
        workflow_mode: "from_scratch",
        creation_origin: "idea_only",
      });
    });
    expect(api.initIntake).toHaveBeenCalledWith("book-1", {
      creation_origin: "idea_only",
      raw_goal_text: "功能测试书稿",
    });
    expect(screen.getByTestId("location").textContent).toBe(
      "/app/books/book-1?intake=1&auto=1",
    );
  });
});
