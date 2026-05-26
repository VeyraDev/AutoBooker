import { client } from "@/api/client";
import type { ChapterReviewResult } from "@/types/review";

const REVIEW_TIMEOUT_MS = 120_000;

export async function reviewChapter(
  bookId: string,
  chapterIndex: number,
  text?: string,
): Promise<ChapterReviewResult> {
  const { data } = await client.post<ChapterReviewResult>(
    `/books/${bookId}/chapters/${chapterIndex}/review`,
    text?.trim() ? { text } : {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}
