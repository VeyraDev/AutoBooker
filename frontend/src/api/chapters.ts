import { client } from "@/api/client";
import type { Chapter, ChapterCreatePayload, ChapterReorderItem } from "@/types/chapter";

/** 叙事宪法生成可能较慢，与大纲生成同级超时 */
const NARRATIVE_ENSURE_TIMEOUT_MS = 180_000;

export type NarrativeEnsureResult = { ok: boolean; generated: boolean };

export async function ensureNarrativeConstitution(bookId: string): Promise<NarrativeEnsureResult> {
  const { data } = await client.post<NarrativeEnsureResult>(
    `/books/${bookId}/narrative/ensure`,
    {},
    { timeout: NARRATIVE_ENSURE_TIMEOUT_MS },
  );
  return data;
}

export async function getChapter(bookId: string, chapterIndex: number): Promise<Chapter> {
  const { data } = await client.get<Chapter>(`/books/${bookId}/chapters/${chapterIndex}`);
  return data;
}

/** 断流/刷新后目录卡在「生成中」时，将本章恢复为待生成（幂等） */
export async function cancelChapterGeneration(bookId: string, chapterIndex: number): Promise<Chapter> {
  const { data } = await client.post<Chapter>(`/books/${bookId}/chapters/${chapterIndex}/cancel-generation`);
  return data;
}

export async function updateChapter(
  bookId: string,
  chapterIndex: number,
  body: {
    title?: string | null;
    summary?: string | null;
    content?: Record<string, unknown> | null;
  },
): Promise<Chapter> {
  const { data } = await client.put<Chapter>(`/books/${bookId}/chapters/${chapterIndex}`, body);
  return data;
}

export async function createChapter(bookId: string, body: ChapterCreatePayload): Promise<Chapter> {
  const { data } = await client.post<Chapter>(`/books/${bookId}/chapters`, body);
  return data;
}

export async function deleteChapter(bookId: string, chapterIndex: number): Promise<void> {
  await client.delete(`/books/${bookId}/chapters/${chapterIndex}`);
}

export async function reorderChapters(bookId: string, items: ChapterReorderItem[]): Promise<Chapter[]> {
  const { data } = await client.patch<Chapter[]>(`/books/${bookId}/chapters/reorder`, { items });
  return data;
}

export type SelectionEditMode = "polish" | "expand" | "shrink" | "dedupe" | "rewrite" | "flowchart";

export async function editChapterSelection(
  bookId: string,
  chapterIndex: number,
  body: {
    mode: SelectionEditMode;
    text: string;
    instruction?: string | null;
    /** 选区前后章节上下文，供模型理解 */
    context?: string | null;
  },
): Promise<{ text: string }> {
  const { data } = await client.post<{ text: string }>(
    `/books/${bookId}/chapters/${chapterIndex}/edit-selection`,
    body,
  );
  return data;
}
