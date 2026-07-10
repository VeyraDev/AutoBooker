import axios from "axios";

import { client } from "./client";

export interface BookJobDetail {
  book_title: string;
  outline_ready: boolean;
  narrative_ready: boolean;
  writing_started: boolean;
  ready_for_editor: boolean;
  total_chapters: number;
  chapters_done: number;
  current_chapter_index: number | null;
  figures_total: number;
  figures_done: number;
  figures_pending: number;
  stage_message: string;
  started_at: string | null;
  elapsed_seconds: number;
  updated_at: string | null;
}

export interface BookJob {
  id: string;
  book_id: string;
  status: string;
  current_step: string | null;
  progress_pct: number;
  error_message: string | null;
  detail?: BookJobDetail | null;
}

/** 对已有书稿启动一键生成 Job */
export async function startAutoGenerateForBook(bookId: string): Promise<BookJob> {
  const { data } = await client.post<BookJob>(`/book-jobs/${bookId}/start`);
  return data;
}

export async function fetchBookJob(bookId: string): Promise<BookJob | null> {
  try {
    const { data } = await client.get<BookJob>(`/book-jobs/${bookId}`);
    return data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) return null;
    throw e;
  }
}
