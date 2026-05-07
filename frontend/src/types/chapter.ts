import type { ChapterGenStatus } from "./book";

export interface Chapter {
  id: string;
  index: number;
  title: string;
  summary: string | null;
  content: Record<string, unknown> | null;
  word_count: number;
  status: ChapterGenStatus;
}

export interface ChapterCreatePayload {
  title?: string;
  summary?: string | null;
  insert_at?: number | null;
}

export interface ChapterReorderItem {
  chapter_id: string;
  new_index: number;
}
