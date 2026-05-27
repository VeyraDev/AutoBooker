import { client } from "@/api/client";
import type { ChapterReviewResult, ReviewActionType, ReviewApplyResult } from "@/types/review";

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

export async function applyReviewIssue(
  bookId: string,
  chapterIndex: number,
  body: {
    action_type: ReviewActionType;
    quote: string;
    suggestion: string;
    detail?: string;
    context?: string;
  },
): Promise<ReviewApplyResult> {
  const { data } = await client.post<ReviewApplyResult>(
    `/books/${bookId}/chapters/${chapterIndex}/review/apply-issue`,
    {
      action_type: body.action_type,
      quote: body.quote,
      suggestion: body.suggestion,
      detail: body.detail ?? "",
      context: body.context ?? "",
    },
    { timeout: 120000 },
  );
  return data;
}
