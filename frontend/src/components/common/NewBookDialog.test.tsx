// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import NewBookDialog from "@/components/common/NewBookDialog";

const api = vi.hoisted(() => ({
  createBook: vi.fn(),
  bootstrapProjectStart: vi.fn(),
  startAutoGenerateForBook: vi.fn(),
}));

vi.mock("@/api/books", () => ({
  createBook: api.createBook,
}));

vi.mock("@/features/intake/api/intakeApi", () => ({
  bootstrapProjectStart: api.bootstrapProjectStart,
}));

vi.mock("@/api/bookJobs", () => ({
  startAutoGenerateForBook: api.startAutoGenerateForBook,
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

describe("NewBookDialog streamlined flow", () => {
  it("继续完善 creates book and opens assistant route", async () => {
    api.createBook.mockResolvedValue({ id: "book-1", title: "书稿1" });
    api.bootstrapProjectStart.mockResolvedValue({
      intake_id: "intake-1",
      status: "collecting",
      writing_basis_id: "basis-1",
    });

    renderDialog();
    const user = userEvent.setup();
    await user.type(
      screen.getByPlaceholderText(/例如：一本面向产品经理/),
      "AI 应用实战书",
    );
    await user.click(screen.getByRole("button", { name: "继续完善" }));

    await waitFor(() => {
      expect(api.createBook).toHaveBeenCalled();
      expect(api.bootstrapProjectStart).toHaveBeenCalledWith("book-1", {
        creation_origin: "idea_only",
        raw_goal_text: "AI 应用实战书",
      });
    });
    expect(screen.getByTestId("location").textContent).toBe("/app/books/book-1");
  });

  it("一键生成 starts auto job and navigates to progress page", async () => {
    api.createBook.mockResolvedValue({ id: "book-2", title: "书稿2" });
    api.bootstrapProjectStart.mockResolvedValue({
      intake_id: "intake-2",
      status: "collecting",
      writing_basis_id: "basis-2",
    });
    api.startAutoGenerateForBook.mockResolvedValue({ id: "job-1", book_id: "book-2", status: "pending" });

    renderDialog();
    const user = userEvent.setup();
    await user.type(
      screen.getByPlaceholderText(/例如：一本面向产品经理/),
      "快速出一本入门书",
    );
    await user.click(screen.getByRole("button", { name: "一键生成" }));

    await waitFor(() => {
      expect(api.startAutoGenerateForBook).toHaveBeenCalledWith("book-2");
    });
    expect(screen.getByTestId("location").textContent).toBe("/app/books/book-2/auto-progress");
  });
});
