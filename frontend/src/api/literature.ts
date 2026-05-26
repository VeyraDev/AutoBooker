import { client } from "@/api/client";
import type {
  CitationRecord,
  LiteraturePaper,
  LiteratureQuoteBlock,
  LiteratureSearchResult,
} from "@/types/literature";

export async function searchLiterature(
  bookId: string,
  query: string,
  rows = 25,
): Promise<LiteratureSearchResult> {
  const { data } = await client.post<LiteratureSearchResult>(
    `/books/${bookId}/literature/search`,
    { query, rows },
    { timeout: 60000 },
  );
  return data;
}

export async function insertSelectedLiteratureQuotes(
  bookId: string,
  papers: LiteraturePaper[],
): Promise<{ quotes: LiteratureQuoteBlock[]; citations: CitationRecord[] }> {
  const { data } = await client.post<{ quotes: LiteratureQuoteBlock[]; citations: CitationRecord[] }>(
    `/books/${bookId}/literature/insert-selected`,
    { papers, source: "literature_search" },
    { timeout: 120000 },
  );
  return data;
}

export async function formatLiteratureCitation(
  bookId: string,
  paper: LiteraturePaper,
  style: string,
  index?: number,
): Promise<string> {
  const { data } = await client.post<{ citation: string }>(`/books/${bookId}/literature/format`, {
    paper,
    style,
    index,
  });
  return data.citation;
}

export async function addSelectedLiterature(
  bookId: string,
  papers: LiteraturePaper[],
): Promise<CitationRecord[]> {
  const { data } = await client.post<{ items: CitationRecord[] }>(
    `/books/${bookId}/literature/add-selected`,
    { papers, source: "literature_search" },
  );
  return data.items;
}
