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
): Promise<{ sentence: string; citation_id: string; node: Record<string, unknown> }> {
  const { data } = await client.post<{ sentence: string; citation_id: string; node: Record<string, unknown> }>(
    `/books/${bookId}/citations/${citationId}/weave`,
    { context },
    { timeout: 90000 },
  );
  return data;
}

export type CitationOccurrence = {
  id: string;
  citation_id: string;
  evidence_id: string | null;
  chapter_id: string;
  chapter_index: number;
  chapter_title: string;
  node_id: string;
  cite_mode: string;
  locator: string | null;
  context_before: string | null;
  context_after: string | null;
  complete: boolean;
  citation: CitationRecord;
};

export async function listCitationOccurrences(bookId: string): Promise<CitationOccurrence[]> {
  const { data } = await client.get<CitationOccurrence[]>(`/books/${bookId}/citation-occurrences`);
  return data;
}

export async function deleteCitationOccurrence(bookId: string, occurrenceId: string): Promise<void> {
  await client.delete(`/books/${bookId}/citation-occurrences/${occurrenceId}`);
}

export async function replaceCitationOccurrence(
  bookId: string,
  occurrenceId: string,
  citationId: string,
): Promise<void> {
  await client.post(`/books/${bookId}/citation-occurrences/${occurrenceId}/replace`, {
    citation_id: citationId,
  });
}

export async function syncBibliographyChapter(bookId: string): Promise<{
  chapter_index: number | null;
  bibliography_text: string;
  message: string;
}> {
  const { data } = await client.post(`/books/${bookId}/citations/sync-bibliography`);
  return data;
}
