import { client } from "@/api/client";
import type { CitationRecord } from "@/types/literature";

export async function listCitations(bookId: string): Promise<CitationRecord[]> {
  const { data } = await client.get<{ items: CitationRecord[] }>(`/books/${bookId}/citations`);
  return data.items;
}

export async function insertCitations(
  bookId: string,
  citationIds: string[],
  syncBibliography = true,
): Promise<{
  in_text_marks: string[];
  bibliography_lines: string[];
  citations: CitationRecord[];
}> {
  const { data } = await client.post<{
    in_text_marks: string[];
    bibliography_lines: string[];
    citations: CitationRecord[];
  }>(`/books/${bookId}/citations/insert`, {
    citation_ids: citationIds,
    sync_bibliography: syncBibliography,
  });
  return data;
}

export async function weaveCitation(
  bookId: string,
  citationId: string,
  context: string,
): Promise<{ sentence: string; citation_id: string }> {
  const { data } = await client.post<{ sentence: string; citation_id: string }>(
    `/books/${bookId}/citations/${citationId}/weave`,
    { context },
    { timeout: 90000 },
  );
  return data;
}

export async function syncBibliographyChapter(bookId: string): Promise<{
  chapter_index: number | null;
  bibliography_text: string;
  message: string;
}> {
  const { data } = await client.post(`/books/${bookId}/citations/sync-bibliography`);
  return data;
}
