import { client } from "./client";

export interface BookJob {
  id: string;
  book_id: string;
  status: string;
  current_step: string | null;
  progress_pct: number;
  error_message: string | null;
}

export async function startAutoGenerate(payload: {
  title: string;
  book_type: string;
  style_type: string;
  discipline?: string | null;
}): Promise<BookJob> {
  const { data } = await client.post<BookJob>("/book-jobs/auto-generate", payload);
  return data;
}

/** 对已有书稿（设定页保存后）启动一键生成 Job */
export async function startAutoGenerateForBook(bookId: string): Promise<BookJob> {
  const { data } = await client.post<BookJob>(`/book-jobs/${bookId}/start`);
  return data;
}

export async function fetchBookJob(bookId: string): Promise<BookJob> {
  const { data } = await client.get<BookJob>(`/book-jobs/${bookId}`);
  return data;
}
