import { describe, expect, it } from "vitest";

import { bookDestination } from "@/lib/bookRoutes";

describe("bookDestination", () => {
  it("routes running one-click books to progress", () => {
    expect(
      bookDestination({
        id: "book-1",
        workflow_mode: "from_scratch",
        status: "auto_generating",
      }),
    ).toBe("/app/books/book-1/auto-progress");
  });

  it("routes optimization books to their dedicated workspace", () => {
    expect(
      bookDestination({
        id: "book-2",
        workflow_mode: "optimize_existing",
        status: "setup",
      }),
    ).toBe("/app/books/book-2/optimize");
  });
});
