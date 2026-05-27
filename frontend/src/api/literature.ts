import { client } from "@/api/client";
import type {
  CitationRecord,
  LiteraturePaper,
  LiteratureQuoteBlock,
  LiteratureRefineResult,
  LiteratureSearchResult,
} from "@/types/literature";

export async function refineLiteratureQuery(
  bookId: string,
  opts: { scope: "book" | "chapter"; chapterIndex?: number; rawQuery?: string },
): Promise<LiteratureRefineResult> {
  const { data } = await client.post<LiteratureRefineResult>(
    `/books/${bookId}/literature/refine-query`,
    {
      scope: opts.scope,
      chapter_index: opts.chapterIndex,
      raw_query: opts.rawQuery ?? "",
    },
    { timeout: 60000 },
  );
  return data;
}

export async function searchLiterature(
  bookId: string,
  opts: {
    query?: string;
    rows?: number;
    refined_queries?: string[];
    must_include?: string[];
    must_exclude?: string[];
    skip_refine?: boolean;
    signal?: AbortSignal;
  },
): Promise<LiteratureSearchResult> {
  const { data } = await client.post<LiteratureSearchResult>(
    `/books/${bookId}/literature/search`,
    {
      query: opts.query ?? "",
      rows: opts.rows ?? 25,
      refined_queries: opts.refined_queries,
      must_include: opts.must_include,
      must_exclude: opts.must_exclude,
      skip_refine: opts.skip_refine ?? false,
    },
    { timeout: 180000, signal: opts.signal },
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
