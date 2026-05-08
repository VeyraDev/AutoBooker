import { client } from "@/api/client";
import type { Chapter, ChapterCreatePayload, ChapterReorderItem } from "@/types/chapter";

export async function getChapter(bookId: string, chapterIndex: number): Promise<Chapter> {
  const { data } = await client.get<Chapter>(`/books/${bookId}/chapters/${chapterIndex}`);
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

export type SelectionEditMode = "polish" | "expand" | "shrink";

export async function editChapterSelection(
  bookId: string,
  chapterIndex: number,
  body: { mode: SelectionEditMode; text: string },
): Promise<{ text: string }> {
  const { data } = await client.post<{ text: string }>(
    `/books/${bookId}/chapters/${chapterIndex}/edit-selection`,
    body,
  );
  return data;
}
