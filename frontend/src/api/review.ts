import { client } from "@/api/client";
import type {
  AiInlinePreviewResult,
  ChapterReviewResult,
  ReviewActionType,
  ReviewApplyResult,
  ReviewConfirmResult,
  ReviewHistoryItem,
} from "@/types/review";

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

export async function getLatestReview(bookId: string, chapterIndex: number): Promise<ChapterReviewResult | null> {
  try {
    const { data } = await client.get<ChapterReviewResult>(
      `/books/${bookId}/chapters/${chapterIndex}/review/latest`,
      { timeout: REVIEW_TIMEOUT_MS },
    );
    return data;
  } catch (error: unknown) {
    if (typeof error === "object" && error && "response" in error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 404) return null;
    }
    throw error;
  }
}

export async function getReviewHistory(bookId: string, chapterIndex: number): Promise<ReviewHistoryItem[]> {
  const { data } = await client.get<ReviewHistoryItem[]>(
    `/books/${bookId}/chapters/${chapterIndex}/review/history`,
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function recheckReview(bookId: string, reviewId: string): Promise<ChapterReviewResult> {
  const { data } = await client.post<ChapterReviewResult>(
    `/books/${bookId}/reviews/${reviewId}/recheck`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function previewReviewIssue(bookId: string, issueId: string): Promise<ReviewApplyResult> {
  const { data } = await client.post<ReviewApplyResult>(
    `/books/${bookId}/review-issues/${issueId}/preview`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function previewReviewIssueDedupe(bookId: string, issueId: string): Promise<ReviewApplyResult> {
  const { data } = await client.post<ReviewApplyResult>(
    `/books/${bookId}/review-issues/${issueId}/dedupe-preview`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function confirmReviewApplication(
  bookId: string,
  applicationId: string,
): Promise<ReviewConfirmResult> {
  const { data } = await client.post<ReviewConfirmResult>(
    `/books/${bookId}/review-applications/${applicationId}/confirm`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function undoReviewApplication(bookId: string, applicationId: string): Promise<ReviewApplyResult> {
  const { data } = await client.post<ReviewApplyResult>(
    `/books/${bookId}/review-applications/${applicationId}/undo`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}

export async function dismissReviewIssue(bookId: string, issueId: string): Promise<ChapterReviewResult | null> {
  const { data } = await client.post<{ review?: ChapterReviewResult | null }>(
    `/books/${bookId}/review-issues/${issueId}/dismiss`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data.review ?? null;
}

export async function resolveReviewIssue(bookId: string, issueId: string): Promise<ChapterReviewResult | null> {
  const { data } = await client.post<{ review?: ChapterReviewResult | null }>(
    `/books/${bookId}/review-issues/${issueId}/resolve`,
    {},
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data.review ?? null;
}

export async function createAiInlinePreview(
  bookId: string,
  chapterIndex: number,
  body: {
    selection: {
      from?: number | null;
      to?: number | null;
      text: string;
      paragraph_id?: string | null;
    };
    instruction: string;
    context_before?: string;
    context_after?: string;
  },
): Promise<AiInlinePreviewResult> {
  const { data } = await client.post<AiInlinePreviewResult>(
    `/books/${bookId}/chapters/${chapterIndex}/ai-inline-preview`,
    body,
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
    { timeout: REVIEW_TIMEOUT_MS },
  );
  return data;
}
