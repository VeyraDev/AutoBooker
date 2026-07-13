// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MemoryPanel from "@/features/memory/MemoryPanel";

vi.mock("@/features/memory/memoryApi", () => ({
  listMemories: vi.fn().mockResolvedValue([
    {
      id: "m1",
      book_id: "b1",
      memory_type: "constraint",
      content: "不要营销腔",
      strength: "must",
      confirmed: true,
      created_at: "2026-07-13T00:00:00Z",
      updated_at: "2026-07-13T00:00:00Z",
    },
  ]),
  patchMemory: vi.fn(),
  deleteMemory: vi.fn(),
  MEMORY_TYPE_LABELS: { constraint: "约束禁令" },
  STRENGTH_LABELS: { must: "必须" },
}));

describe("MemoryPanel", () => {
  it("renders memory list", async () => {
    render(<MemoryPanel bookId="b1" />);
    expect(await screen.findByText("不要营销腔")).toBeTruthy();
    expect(screen.getByText("约束禁令")).toBeTruthy();
  });
});
