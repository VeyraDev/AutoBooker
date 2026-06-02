import { client } from "./client";

export interface GlobalLiteratureItem {
  id: string;
  source: string;
  title: string;
  authors: string[];
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
  url?: string | null;
  abstract?: string | null;
  tags: string[];
  contributor_name?: string | null;
  cite_count: number;
}

export async function listGlobalLibrary(params?: {
  source?: string;
  tag?: string;
  q?: string;
  mine?: boolean;
}): Promise<{ items: GlobalLiteratureItem[]; total: number }> {
  const { data } = await client.get("/library", { params });
  return data;
}

export async function addLibraryToBook(bookId: string, literatureId: string): Promise<void> {
  await client.post(`/library/books/${bookId}/add`, { literature_id: literatureId });
}
