import { client } from "@/api/client";
import type {
  CitationRecord,
  CitationVerificationDueJobRequest,
  CitationVerificationDueJobResult,
  CitationVerificationJob,
} from "@/types/literature";

export async function listCitations(bookId: string): Promise<CitationRecord[]> {
  const { data } = await client.get<{ items: CitationRecord[] }>(`/books/${bookId}/citations`);
  return data.items;
}

export async function refreshCitationVerification(
  bookId: string,
  citationId: string,
): Promise<CitationRecord> {
  const { data } = await client.post<CitationRecord>(`/books/${bookId}/citations/${citationId}/verify`);
  return data;
}

export async function refreshCitationVerifications(
  bookId: string,
  citationIds?: string[],
): Promise<CitationRecord[]> {
  const payload = citationIds?.length ? { citation_ids: citationIds } : {};
  const { data } = await client.post<{ items: CitationRecord[] }>(`/books/${bookId}/citations/verify`, payload);
  return data.items;
}

export async function startCitationVerificationJob(
  bookId: string,
  citationIds?: string[],
  retryUnreachableOnly = false,
): Promise<CitationVerificationJob> {
  const payload = {
    ...(citationIds?.length ? { citation_ids: citationIds } : {}),
    retry_unreachable_only: retryUnreachableOnly,
  };
  const { data } = await client.post<CitationVerificationJob>(`/books/${bookId}/citations/verify-jobs`, payload);
  return data;
}

export async function startDueCitationVerificationJob(
  bookId: string,
  options: CitationVerificationDueJobRequest = {},
): Promise<CitationVerificationDueJobResult> {
  const { data } = await client.post<CitationVerificationDueJobResult>(
    `/books/${bookId}/citations/verify-jobs/due`,
    options,
  );
  return data;
}

export async function getCitationVerificationJob(
  bookId: string,
  jobId: string,
): Promise<CitationVerificationJob> {
  const { data } = await client.get<CitationVerificationJob>(`/books/${bookId}/citations/verify-jobs/${jobId}`);
  return data;
}

export async function listCitationVerificationJobs(bookId: string): Promise<CitationVerificationJob[]> {
  const { data } = await client.get<CitationVerificationJob[]>(`/books/${bookId}/citations/verify-jobs`);
  return data;
}

export async function insertCitations(
  bookId: string,
  citationIds: string[],
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
