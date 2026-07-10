// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReviewStagePage from "@/features/reviewStage/ReviewStagePage";

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

function renderPage(onCompleteBook = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ReviewStagePage bookId="book-1" onCompleteBook={onCompleteBook} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReviewStagePage", () => {
  it("lets users complete the book without running review", async () => {
    const onCompleteBook = vi.fn();
    api.get.mockImplementation((url: string) => {
      if (url.endsWith("/summary")) {
        return Promise.resolve({
          data: {
            tracks: {
              writing_quality: { status: "not_started" },
              publication_standard: { status: "not_started" },
            },
            suggestion_count: 0,
          },
        });
      }
      if (url.endsWith("/findings")) {
        return Promise.resolve({ data: { findings: [] } });
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });

    renderPage(onCompleteBook);

    expect(await screen.findByText(/待审校/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "完成全书" }));

    await waitFor(() => {
      expect(onCompleteBook).toHaveBeenCalledTimes(1);
    });
    expect(api.post).not.toHaveBeenCalled();
  });
});
