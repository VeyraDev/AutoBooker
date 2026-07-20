import { beforeEach, describe, expect, it, vi } from "vitest";

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/api/client", () => ({
  client: { get },
}));

import { loadFigureImageBlob, resolveFigureUrl } from "@/api/figures";

describe("figure asset URLs", () => {
  beforeEach(() => {
    get.mockReset();
  });

  it("normalizes legacy /api asset URLs to the mounted books route", () => {
    expect(
      resolveFigureUrl(
        "/api/books/11111111-1111-1111-1111-111111111111/assets/22222222-2222-2222-2222-222222222222/content",
        7,
      ),
    ).toBe(
      "/books/11111111-1111-1111-1111-111111111111/assets/22222222-2222-2222-2222-222222222222/content?v=7",
    );
  });

  it("loads protected assets through the authenticated API client", async () => {
    const blob = new Blob(["image"], { type: "image/png" });
    get.mockResolvedValue({ data: blob });

    await expect(loadFigureImageBlob("/books/book/assets/asset/content", 9)).resolves.toBe(blob);
    expect(get).toHaveBeenCalledWith(
      "/books/book/assets/asset/content?v=9",
      expect.objectContaining({ responseType: "blob" }),
    );
  });
});
