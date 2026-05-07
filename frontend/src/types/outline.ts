import type { ChapterGenStatus } from "./book";

export interface OutlineSection {
  title: string;
  summary: string;
}

export interface OutlineChapter {
  id: string;
  index: number;
  title: string;
  summary: string | null;
  key_points: string[];
  estimated_words: number;
  sections: OutlineSection[];
  word_count: number;
  status: ChapterGenStatus;
}

export interface OutlineBookResponse {
  title: string;
  total_chapters: number;
  estimated_words: number;
  chapters: OutlineChapter[];
}

export interface OutlineChapterPatch {
  index: number;
  title?: string | null;
  summary?: string | null;
  key_points?: string[] | null;
  estimated_words?: number | null;
  sections?: OutlineSection[] | null;
}

export interface OutlinePutPayload {
  chapters: OutlineChapterPatch[];
  confirm_start_writing?: boolean;
}

export interface OutlineGeneratePayload {
  topic_override?: string | null;
  target_audience?: string | null;
}
